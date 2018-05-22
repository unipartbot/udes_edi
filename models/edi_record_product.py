import logging

from odoo import api, fields, models
from odoo.tools.translate import _
from .tools import range_chunk

_logger = logging.getLogger(__name__)

PRODUCT_CHUNK_SIZE = 1000


class EdiDocumentType(models.Model):

    _inherit = 'edi.document.type'

    x_use_product = fields.Boolean(string='Use Product Records',
                                   compute='_compute_use_product', store=True)

    @api.one
    @api.depends('rec_type_ids')
    def _compute_use_product(self):
        """Compute use of Product records"""
        self.compute_use_record('x_use_product', 'udes.edi.record.product')


class EdiDocument(models.Model):

    _inherit = 'edi.document'

    x_product_ids = fields.One2many('udes.edi.record.product', 'doc_id',
                                    string='Products')
    x_use_product = fields.Boolean(related='doc_type_id.x_use_product')


class EdiProduct(models.Model):

    _name = 'udes.edi.record.product'
    _inherit = 'edi.record'
    _description = 'Product'

    product_id = fields.Many2one('product.product', string='Product',
                                 required=False, readonly=True, index=True,
                                 auto_join=True)
    description = fields.Char(string='Description', required=True,
                              readonly=True, default='Unknown')
    weight = fields.Float(string='Weight', required=True, readonly=True,
                          default=0.0)
    volume = fields.Float(string='Volume', required=True, readonly=True,
                          default=0.0)
    tracking = fields.Selection([('serial', 'By Serial Number'),
                                 ('lot', 'By Lots'),
                                 ('none', 'No Tracking')],
                                string="Tracking", required=True,
                                readonly=True, default='none')

    @api.multi
    def _product_vals(self):
        self.ensure_one()
        return {
            'active': True,
            'name': self.description,
            'default_code': self.name,
            'barcode': self.name,
            'weight': self.weight,
            'volume': self.volume,
            'tracking': self.tracking,
            }

    @api.multi
    def execute(self):
        """Execute product records"""
        super(EdiProduct, self).execute()
        doc = self.mapped('doc_id')

        # Update existing products
        for r, chunk in range_chunk(self.filtered(lambda x: x.product_id),
                                    PRODUCT_CHUNK_SIZE):
            _logger.info(_('%s updating %d-%d'), doc.name, r[0], r[-1])
            for rec in chunk:
                rec.product_id.write(rec._product_vals())

        # Create new products
        Product = self.env['product.product'].with_context({
            'tracking_disable': True,
            })
        for r, chunk in range_chunk(self.filtered(lambda x: not x.product_id),
                                    PRODUCT_CHUNK_SIZE):
            _logger.info(_('%s creating %d-%d'), doc.name, r[0], r[-1])
            for rec in chunk:
                rec.product_id = Product.create(rec._product_vals())
