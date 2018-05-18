{
    'name': 'EDI Formats',
    'summary': 'Standard EDI Document Formats',
    'description': """Standard EDI Document Formats""",

    'author': 'Unipart Digital Team',
    'website': 'https://unipart.io',
    'category': 'Specific Industry Applications',
    'application': False,
    'version': '0.1',
    'depends': ['product',
                'stock',  # product.product.tracking is added by stock module.
                'edi'],
    'data': [
             # 'security/ir.model.access.csv',
             'data/pmd_data.xml',
             'views/edi_product_views.xml',
             ],
}
