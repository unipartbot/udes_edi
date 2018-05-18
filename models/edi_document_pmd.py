import csv
import logging
import re
from base64 import b64decode

from odoo import api, models
from odoo.exceptions import UserError
from odoo.tools import float_compare
from odoo.tools.translate import _
from .tools import range_chunk

_logger = logging.getLogger(__name__)

CHUNK_SIZE = 1000
ROUNDING = 0.01


class ProductMasterDataIterator(object):

    def __init__(self, reader):
        self.reader = reader

    def __iter__(self):
        # This is a one-shot iterator, since we cannot cleanly rewind
        # the underlying reader.
        for (material_number, material_description, weight, length, width,
             height, serial) in self.reader:
            # Construct result
            yield (material_number,
                   material_description,
                   (float(weight) if weight else 0.0),
                   ((float(length) * float(width) * float(height) / 1000000.0)
                    if length and width and height else 0.0),
                   ('serial' if serial.lower() == 'y' else 'none'))


class EdiDocumentPmd(models.AbstractModel):

    _name = 'udes.edi.document.pmd'
    _description = 'Product Master Data'

    @api.model
    def autotype(self, inputs):
        """Autodetect document type"""
        return [x for x in inputs if re.match(r'^PMD', x.datas_fname)]

    @api.model
    def _prepare_chunk(self, doc, chunk):
        """Prepare document chunk"""
        Product = self.env['product.product'].with_context(active_test=False)
        Template = self.env['product.template'].with_context(active_test=False)
        EdiProduct = self.env['udes.edi.record.product']

        # Look up existing products
        products_search = list(map(lambda x: x[0], chunk))
        products = Product.search([('default_code', 'in', products_search)])
        products_by_code = {x.default_code: x for x in products}

        # Cache product templates to minimise database lookups
        templates = Template.browse(products.mapped('product_tmpl_id.id'))
        templates.mapped('name')

        # Create EDI records
        for (material_number, material_description, weight, volume, tracking) in chunk:
            # Skip unchanged products
            product = products_by_code.get(material_number)
            if (product and product.active and
                (material_number == product.barcode) and
                (material_description == product.name) and
                (float_compare(weight, product.weight,
                               precision_rounding=ROUNDING) == 0) and
                (float_compare(volume, product.volume,
                               precision_rounding=ROUNDING) == 0) and
                (tracking == product.tracking)):
                    continue

            # Create EDI product record
            EdiProduct.create({
                'doc_id': doc.id,
                'name': material_number,
                'product_id': product and product.id,
                'description': material_description,
                'weight': weight,
                'volume': volume,
                'tracking': tracking,
                })

    @api.model
    def prepare(self, doc):
        """Prepare document"""

        # Parse attachments
        if not doc.input_ids:
            raise UserError(_('Missing input attachment'))
        lines = (line.decode()
                 for attachment in doc.input_ids
                 for line in b64decode(attachment.datas).splitlines())
        pmd = ProductMasterDataIterator(csv.reader(lines))

        # Process in chunks
        for r, chunk in range_chunk(pmd, CHUNK_SIZE):
            _logger.info(_('%s preparing %d-%d'), doc.name, r[0], r[-1])
            self._prepare_chunk(doc, chunk)
