from odoo import models, fields, _


class ImportPaymentLineWizard(models.TransientModel):
    _name = 'import.payment.line.wizard'
    _description = 'Agregar Compromiso de Pago'

    report_id = fields.Many2one('import.payment.report', string='Reporte', required=True)
    partner_id = fields.Many2one('res.partner', string='Proveedor / Forwarder', required=True)
    name = fields.Char(string='Descripción', required=True)
    commitment_category = fields.Selection([
        ('credit_import', 'Vencimiento Crédito — Importación'),
        ('credit_freight_sea', 'Flete Marítimo'),
        ('credit_freight_land', 'Flete Terrestre'),
        ('advance', 'Anticipo'),
        ('balance', 'Balance / Liquidación'),
        ('import_tax', 'Impuesto de Importación'),
    ], string='Categoría', required=True, default='credit_import')

    amount_original = fields.Float(string='Monto', required=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', required=True,
                                   default=lambda self: self.env.ref('base.USD'))
    due_date = fields.Date(string='Fecha Vencimiento')
    eta_date = fields.Date(string='ETA')
    invoice_reference = fields.Char(string='No. Factura')
    purchase_order_id = fields.Many2one('purchase.order', string='Orden de Compra')
    bl_number = fields.Char(string='Número BL')
    container_numbers = fields.Char(string='Contenedores')
    sales_orders = fields.Char(string='Órdenes de Venta')
    payment_term_type = fields.Char(string='Término de Pago')
    note = fields.Text(string='Notas')
    tax_amount_mxn = fields.Float(string='Impuestos MXN')
    tax_is_estimate = fields.Boolean(string='Es Estimado', default=True)
    payment_programmed_date = fields.Date(string='Fecha Pago Programado')

    def action_confirm(self):
        self.ensure_one()
        self.env['import.payment.line'].create({
            'report_id': self.report_id.id,
            'partner_id': self.partner_id.id,
            'name': self.name,
            'commitment_category': self.commitment_category,
            'amount_original': self.amount_original,
            'currency_id': self.currency_id.id,
            'due_date': self.due_date,
            'eta_date': self.eta_date,
            'invoice_reference': self.invoice_reference,
            'purchase_order_id': self.purchase_order_id.id if self.purchase_order_id else False,
            'bl_number': self.bl_number,
            'container_numbers': self.container_numbers,
            'sales_orders': self.sales_orders,
            'payment_term_type': self.payment_term_type,
            'note': self.note,
            'tax_amount_mxn': self.tax_amount_mxn,
            'tax_is_estimate': self.tax_is_estimate,
            'payment_programmed_date': self.payment_programmed_date,
        })
        return {'type': 'ir.actions.client', 'tag': 'reload'}
