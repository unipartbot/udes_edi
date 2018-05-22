import csv
import os.path
from base64 import b64encode

from odoo.models import BaseModel
from odoo.tests import common
from odoo.tools import float_compare

# relative to current directory
FILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'files/pmd')

ROUNDING = 0.01


class TestPmd(common.SavepointCase):
    @classmethod
    def setUpClass(cls):
        super(TestPmd, cls).setUpClass()
        cls.doc_type_pmd = cls.env.ref('udes_edi.edi_document_type_pmd')

    def assertRecsEqual(self, rec1, rec2):
        """Assert that recordsets are equal"""
        self.assertSameModel(rec1, rec2)
        self.assertItemsEqual(rec1.ids, rec2.ids)

    def assertNoIssues(self, issues):
        """Assert that a list of issues is empty
        Assert that a list of issues is empty, including the issue
        names in the failure message if applicable.
        """
        self.assertIsModel(issues, 'project.task')
        self.assertFalse(issues, msg=issues.mapped('name'))

    def assertSameModel(self, *args):
        """Assert that all arguments are recordsets of the same model"""
        for arg in args:
            self.assertIsInstance(arg, BaseModel)
        for arg in args:
            self.assertEqual(arg._name, args[0]._name)

    def assertIsModel(self, recs, model):
        """Assert that recordset belongs to model.

        :param recs: The recordset to test.
        :type recs: BaseModel
        :param model: The name of the model, or an instance of the model,
                        that recs must belong to.
        :type model: basestring or BaseModel
        """
        if isinstance(model, BaseModel):
            self.assertSameModel(recs, model)
        elif isinstance(model, str):
            self.assertSameModel(recs, recs.env[model])
        else:
            self.fail(msg='%s is not a valid model' % model)

    def assertProductData(self, product, barcode, name, weight, volume, tracking):
        """Assert that the data for the given product matches what's
        expected."""
        product.ensure_one()
        self.assertEqual(product.barcode, barcode)
        self.assertEqual(product.default_code, barcode)
        self.assertEqual(product.name, name)
        self.assertEqual(float_compare(product.weight, weight, precision_rounding=ROUNDING), 0)
        self.assertEqual(float_compare(product.volume, volume, precision_rounding=ROUNDING), 0)
        self.assertEqual(product.tracking, tracking)

    def create_attachment_from_file(self, file_name, edi_doc, res_field='input_ids'):
        """Create and return an ir.attachment for the file."""
        Attachment = self.env['ir.attachment']

        with open(os.path.join(FILE_DIR, file_name), 'rb') as content_file:
            file_data = b64encode(content_file.read())

        attachment = Attachment.create({
            'name': file_name,
            'type': 'binary',
            'datas': file_data,
            'datas_fname': file_name,
            'res_model': edi_doc._name,
            'res_field': res_field,
            'res_id': edi_doc.id,
            'res_name': edi_doc.name
        })
        return attachment

    def create_pmd_doc(self, file_name):
        """Create and return an EDI Document record for the file."""
        Document = self.env['edi.document']

        doc = Document.create({'doc_type_id': self.doc_type_pmd.id})
        attachment = self.create_attachment_from_file(file_name, doc)

        self.assertEqual(doc.input_ids[0], attachment)
        doc.action_prepare()
        self.assertNoIssues(doc.issue_ids)
        return doc

    def do_pmd(self, file_name, num_records, num_new_records):
        """Create and execute a PMD document and check it's doing about the
        right thing along the way"""
        doc = self.create_pmd_doc(file_name)

        # 2 EDI Product Records created, none related to existing products.
        self.assertEqual(len(doc.x_product_ids), num_records)
        self.assertEqual(len(doc.x_product_ids.mapped('product_id')), num_records - num_new_records)

        doc.action_execute()
        self.assertNoIssues(doc.issue_ids)

        # products created/updated
        self.assertEqual(len(doc.x_product_ids.mapped('product_id')), num_records)

        return doc

    def test01_test_pmd(self):
        """Test processing of Product Master Data files.
        First test creating new products, then test updating them, then create
        some more in a file that doesn't list the first two, then finally test
        all operations in the same PMD file."""
        Product = self.env['product.product']

        # Create and verify two new products
        self.do_pmd('PMD_TEST_1_NEW.CSV', 2, 2)
        prod1 = Product.search([('barcode', '=', "PMD-TEST-001")])  # Created
        self.assertProductData(prod1,
                               "PMD-TEST-001",
                               "PMD Test Product 001",
                               0.00,
                               0.00,
                               'serial')
        prod2 = Product.search([('barcode', '=', "PMD-TEST-002")])  # Created
        self.assertProductData(prod2,
                               "PMD-TEST-002",
                               "PMD Test Product 002",
                               0.00,
                               0.00,
                               'none')

        # Check changes are correct: prod1 has new weight + volume,
        self.do_pmd('PMD_TEST_2_UPDATE.CSV', 1, 0)
        self.assertProductData(prod1,
                               "PMD-TEST-001",
                               "PMD Test Product 001",
                               0.10,  # Updated
                               0.50,  # Updated
                               'serial')
        self.assertProductData(prod2,
                               "PMD-TEST-002",
                               "PMD Test Product 002",
                               0.00,
                               0.00,
                               'none')

        # Create 2 new products in a file that does not list the two old ones
        # Check the new products are correct: prod3 has weight + volume,
        # prod4 does not.
        self.do_pmd('PMD_TEST_3_NEW.CSV', 2, 2)
        prod3 = Product.search([('barcode', '=', "PMD-TEST-003")])  # Created
        self.assertProductData(prod3,
                               "PMD-TEST-003",
                               "PMD Test Product 003",
                               0.50,
                               0.01,
                               'none')
        prod4 = Product.search([('barcode', '=', "PMD-TEST-004")])  # Created
        self.assertProductData(prod4,
                               "PMD-TEST-004",
                               "PMD Test Product 004",
                               0.00,
                               0.00,
                               'none')

        # One file that misses out prod1, updates prod2 and creates prod5.
        # Check all operations occur when in the same file.
        self.do_pmd('PMD_TEST_4_ALL.CSV', 2, 1)
        self.assertProductData(prod1,
                               "PMD-TEST-001",
                               "PMD Test Product 001",
                               0.10,
                               0.50,
                               'serial')
        self.assertProductData(prod2,
                               "PMD-TEST-002",
                               "PMD Test Product 002",
                               1.00,  # Updated
                               0.00,
                               'none')
        self.assertProductData(prod3,
                               "PMD-TEST-003",
                               "PMD Test Product 003",
                               0.50,
                               0.01,
                               'none')
        self.assertProductData(prod4,
                               "PMD-TEST-004",
                               "PMD Test Product 004",
                               0.00,
                               0.00,
                               'none')
        prod5 = Product.search([('barcode', '=', "PMD-TEST-005")])
        self.assertProductData(prod5,
                               "PMD-TEST-005",
                               "PMD Test Product 005",
                               0.00,
                               0.00,
                               'serial')

    def test02_autotype(self):
        """Create several ir.attachments and check they are correctly identified
        as PMD where appropriate.
        PMD filenames must start with 'PMD'. There is no other restriction."""
        Attachment = self.env['ir.attachment']

        match_1 = Attachment.create({'name': 'TEST1',
                                     'datas_fname': 'PMD_TEST_1.CSV'})  # Simple match
        match_2 = Attachment.create({'name': 'TEST1',
                                     'datas_fname': 'PMD_5.CSV.bak'})  # new extension, still matches.
        mismatch_1 = Attachment.create({'name': 'TEST2',
                                        'datas_fname': 'pmd_test_2.csv'})  # case mismatch
        mismatch_2 = Attachment.create({'name': 'TEST1',
                                        'datas_fname': 'ODQ_TEST_3.CSV'})  # string mismatch
        mismatch_3 = Attachment.create({'name': 'TEST1',
                                        'datas_fname': 'TEST_PMD_4.CSV'})  # start of name mismatch

        test_attachments = (match_1 | match_2 | mismatch_1 | mismatch_2 | mismatch_3)

        DocumentModel = self.env[self.doc_type_pmd.model_id.model]
        matches = DocumentModel.autotype(test_attachments)

        self.assertEqual(len(matches), 2)
        self.assertTrue(match_1 in matches)
        self.assertTrue(match_2 in matches)
