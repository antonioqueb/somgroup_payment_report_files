from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import date, timedelta
import logging

_logger = logging.getLogger(__name__)


class ImportPaymentLine(models.Model):
    """
    Cada registro representa un compromiso de pago en el reporte mensual.
    Categorías: vencimiento crédito importación, flete terrestre, flete marítimo,
    anticipo, balance, impuesto de importación.
    """
    _name = 'import.payment.line'
    _description = 'Línea del Reporte de Pagos a Proveedores'
    _order = 'target_month, commitment_category, due_date, id'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ─── Identificación ──────────────────────────────────────────────────────

    name = fields.Char(
        string='Descripción',
        required=True,
        tracking=True,
    )
    report_id = fields.Many2one(
        'import.payment.report',
        string='Reporte Mensual',
        ondelete='cascade',
        index=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Proveedor / Forwarder',
        required=True,
        tracking=True,
    )

    # ─── Categoría del compromiso ────────────────────────────────────────────

    commitment_category = fields.Selection([
        ('credit_import', 'Vencimiento Crédito — Importación'),
        ('credit_freight_sea', 'Vencimiento Crédito — Flete Marítimo'),
        ('credit_freight_land', 'Vencimiento Crédito — Flete Terrestre'),
        ('advance', 'Anticipo'),
        ('balance', 'Balance / Liquidación'),
        ('import_tax', 'Impuesto de Importación'),
    ], string='Categoría',
       required=True,
       tracking=True,
    )

    # ─── Montos ──────────────────────────────────────────────────────────────

    amount_original = fields.Monetary(
        string='Monto Original',
        currency_field='currency_id',
        required=True,
        tracking=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        required=True,
        default=lambda self: self.env.ref('base.USD'),
        tracking=True,
    )
    amount_usd = fields.Monetary(
        string='Total USD',
        currency_field='currency_usd_id',
        compute='_compute_amounts_converted',
        store=True,
    )
    amount_mxn = fields.Monetary(
        string='Total MXN',
        currency_field='currency_mxn_id',
        compute='_compute_amounts_converted',
        store=True,
    )
    currency_usd_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.ref('base.USD'),
        store=True,
    )
    currency_mxn_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.ref('base.MXN'),
        store=True,
    )

    # Impuestos MXN (solo para categoría import_tax)
    tax_amount_mxn = fields.Float(
        string='Impuestos MXN',
        digits=(12, 2),
    )
    tax_is_estimate = fields.Boolean(
        string='Es Estimado',
        default=True,
    )

    # ─── Fechas y vencimiento ────────────────────────────────────────────────

    due_date = fields.Date(string='Fecha Vencimiento', tracking=True)
    target_month = fields.Char(
        string='Mes Destino',
        compute='_compute_target_month',
        store=True,
        index=True,
    )
    target_month_display = fields.Char(
        string='Mes',
        compute='_compute_target_month',
        store=True,
    )
    eta_date = fields.Date(string='ETA')
    payment_programmed_date = fields.Date(string='Pago Programado')

    # ─── Documentos de referencia ────────────────────────────────────────────

    invoice_reference = fields.Char(string='No. Factura / Referencia', tracking=True)
    purchase_order_id = fields.Many2one('purchase.order', string='Orden de Compra', index=True)
    purchase_order_name = fields.Char(related='purchase_order_id.name', store=True)
    account_move_id = fields.Many2one('account.move', string='Factura Contable')
    bl_number = fields.Char(string='Número BL')
    container_numbers = fields.Char(string='Contenedores')
    sales_orders = fields.Char(string='Órdenes de Venta')

    # ─── Estado ──────────────────────────────────────────────────────────────

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('pending', 'Pendiente'),
        ('partial', 'Pago Parcial'),
        ('paid', 'Pagado'),
        ('overdue', 'Vencido'),
    ], string='Estado', default='pending', tracking=True,
       compute='_compute_state', store=True, readonly=False)

    paid_date = fields.Date(string='Fecha Pago Real', tracking=True)
    paid_amount = fields.Monetary(string='Monto Pagado', currency_field='currency_id', default=0.0)
    remaining_amount = fields.Monetary(
        string='Saldo Pendiente', currency_field='currency_id',
        compute='_compute_remaining', store=True,
    )
    payment_ids = fields.Many2many(
        'account.payment', 'import_payment_line_payment_rel',
        'line_id', 'payment_id', string='Pagos Contables',
    )

    # ─── Alertas ─────────────────────────────────────────────────────────────

    days_until_due = fields.Integer(string='Días para Vencer', compute='_compute_alert')
    alert_level = fields.Selection([
        ('none', 'Sin Alerta'), ('info', 'Próximo'),
        ('warning', 'Urgente'), ('danger', 'Vencido'), ('success', 'Pagado'),
    ], string='Nivel Alerta', compute='_compute_alert')

    # ─── Notas ───────────────────────────────────────────────────────────────

    note = fields.Text(string='Notas')
    payment_term_type = fields.Char(string='Término de Pago')

    # ═══════════════════════════════════════════════════════════════════════════
    # COMPUTES
    # ═══════════════════════════════════════════════════════════════════════════

    @api.depends('due_date', 'payment_programmed_date')
    def _compute_target_month(self):
        month_names = {
            1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
            5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
            9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
        }
        for rec in self:
            ref_date = rec.due_date or rec.payment_programmed_date
            if ref_date:
                rec.target_month = ref_date.strftime('%Y-%m')
                rec.target_month_display = f"{month_names.get(ref_date.month, '')} {ref_date.year}"
            else:
                rec.target_month = False
                rec.target_month_display = 'Sin Fecha'

    @api.depends('amount_original', 'currency_id', 'due_date')
    def _compute_amounts_converted(self):
        usd = self.env.ref('base.USD')
        mxn = self.env.ref('base.MXN')
        for rec in self:
            if not rec.currency_id or not rec.amount_original:
                rec.amount_usd = 0.0
                rec.amount_mxn = 0.0
                continue
            ref_date = rec.due_date or fields.Date.today()
            company = rec.env.company
            if rec.currency_id == usd:
                rec.amount_usd = rec.amount_original
                rec.amount_mxn = usd._convert(rec.amount_original, mxn, company, ref_date)
            elif rec.currency_id == mxn:
                rec.amount_mxn = rec.amount_original
                rec.amount_usd = mxn._convert(rec.amount_original, usd, company, ref_date)
            else:
                # EUR u otra → convertir
                rec.amount_usd = rec.currency_id._convert(rec.amount_original, usd, company, ref_date)
                rec.amount_mxn = rec.currency_id._convert(rec.amount_original, mxn, company, ref_date)

    @api.depends('amount_original', 'paid_amount')
    def _compute_remaining(self):
        for rec in self:
            rec.remaining_amount = max(0.0, (rec.amount_original or 0.0) - (rec.paid_amount or 0.0))

    @api.depends('paid_amount', 'amount_original', 'due_date', 'paid_date')
    def _compute_state(self):
        today = date.today()
        for rec in self:
            if rec.paid_amount and rec.paid_amount >= rec.amount_original:
                rec.state = 'paid'
            elif rec.paid_amount and rec.paid_amount > 0:
                rec.state = 'partial'
            elif rec.due_date and rec.due_date < today:
                rec.state = 'overdue'
            else:
                rec.state = 'pending'

    @api.depends('due_date', 'state')
    def _compute_alert(self):
        today = date.today()
        for rec in self:
            if rec.state == 'paid':
                rec.days_until_due = 0
                rec.alert_level = 'success'
            elif rec.due_date:
                delta = (rec.due_date - today).days
                rec.days_until_due = delta
                if delta < 0:
                    rec.alert_level = 'danger'
                elif delta <= 7:
                    rec.alert_level = 'warning'
                elif delta <= 15:
                    rec.alert_level = 'info'
                else:
                    rec.alert_level = 'none'
            else:
                rec.days_until_due = 0
                rec.alert_level = 'none'

    # ═══════════════════════════════════════════════════════════════════════════
    # ACCIONES
    # ═══════════════════════════════════════════════════════════════════════════

    def action_mark_paid(self):
        today = date.today()
        for rec in self:
            rec.write({
                'paid_amount': rec.amount_original,
                'paid_date': rec.paid_date or today,
            })

    def action_register_payment(self):
        self.ensure_one()
        if self.state == 'paid':
            raise UserError(_('Este compromiso ya está pagado.'))

        if self.account_move_id and self.account_move_id.state == 'posted':
            return {
                'name': _('Registrar Pago'),
                'type': 'ir.actions.act_window',
                'res_model': 'account.payment.register',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'active_model': 'account.move',
                    'active_ids': [self.account_move_id.id],
                    'default_amount': self.remaining_amount or self.amount_original,
                },
            }

        if self.purchase_order_id:
            invoices = self.purchase_order_id.invoice_ids.filtered(
                lambda inv: inv.move_type == 'in_invoice'
                and inv.state == 'posted'
                and inv.payment_state in ('not_paid', 'partial')
            )
            if invoices:
                return {
                    'name': _('Registrar Pago'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'account.payment.register',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'active_model': 'account.move',
                        'active_ids': invoices.ids,
                        'default_amount': min(
                            self.remaining_amount or self.amount_original,
                            sum(invoices.mapped('amount_residual'))
                        ),
                    },
                }

        return {
            'name': _('Registrar Pago Directo'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_payment_type': 'outbound',
                'default_partner_type': 'supplier',
                'default_partner_id': self.partner_id.id,
                'default_amount': self.remaining_amount or self.amount_original,
                'default_currency_id': self.currency_id.id,
                'default_date': fields.Date.today(),
                'default_ref': f'{self.name} — {self.invoice_reference or ""}',
            },
        }
