from odoo import models, fields, api, _
from datetime import date
import logging

_logger = logging.getLogger(__name__)


class ImportPaymentReport(models.Model):
    """
    Reporte mensual consolidado. Equivale a una hoja del Excel de Ana.
    """
    _name = 'import.payment.report'
    _description = 'Reporte Mensual de Pagos — Importaciones'
    _order = 'year desc, month desc'
    _inherit = ['mail.thread']

    name = fields.Char(string='Nombre', compute='_compute_name', store=True)
    month = fields.Selection([
        ('01', 'Enero'), ('02', 'Febrero'), ('03', 'Marzo'),
        ('04', 'Abril'), ('05', 'Mayo'), ('06', 'Junio'),
        ('07', 'Julio'), ('08', 'Agosto'), ('09', 'Septiembre'),
        ('10', 'Octubre'), ('11', 'Noviembre'), ('12', 'Diciembre'),
    ], string='Mes', required=True, tracking=True)
    year = fields.Integer(string='Año', required=True, default=lambda self: date.today().year)
    state = fields.Selection([
        ('draft', 'Borrador'), ('open', 'Activo'), ('closed', 'Cerrado'),
    ], string='Estado', default='draft', tracking=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    # ─── Líneas ──────────────────────────────────────────────────────────────

    line_ids = fields.One2many('import.payment.line', 'report_id', string='Compromisos')

    # ─── Resumen Ejecutivo ───────────────────────────────────────────────────

    currency_usd_id = fields.Many2one('res.currency', default=lambda self: self.env.ref('base.USD'))
    currency_mxn_id = fields.Many2one('res.currency', default=lambda self: self.env.ref('base.MXN'))

    total_credit_import_usd = fields.Monetary(compute='_compute_summary', store=True, currency_field='currency_usd_id')
    total_credit_import_mxn = fields.Monetary(compute='_compute_summary', store=True, currency_field='currency_mxn_id')
    total_freight_sea_usd = fields.Monetary(compute='_compute_summary', store=True, currency_field='currency_usd_id')
    total_freight_sea_mxn = fields.Monetary(compute='_compute_summary', store=True, currency_field='currency_mxn_id')
    total_freight_land_mxn = fields.Monetary(compute='_compute_summary', store=True, currency_field='currency_mxn_id')
    total_advance_usd = fields.Monetary(compute='_compute_summary', store=True, currency_field='currency_usd_id')
    total_advance_mxn = fields.Monetary(compute='_compute_summary', store=True, currency_field='currency_mxn_id')
    total_balance_usd = fields.Monetary(compute='_compute_summary', store=True, currency_field='currency_usd_id')
    total_balance_mxn = fields.Monetary(compute='_compute_summary', store=True, currency_field='currency_mxn_id')
    total_tax_mxn = fields.Monetary(compute='_compute_summary', store=True, currency_field='currency_mxn_id')
    grand_total_usd = fields.Monetary(compute='_compute_summary', store=True, currency_field='currency_usd_id')
    grand_total_mxn = fields.Monetary(compute='_compute_summary', store=True, currency_field='currency_mxn_id')

    total_lines = fields.Integer(compute='_compute_summary', store=True)
    paid_lines = fields.Integer(compute='_compute_summary', store=True)
    pending_lines = fields.Integer(compute='_compute_summary', store=True)
    overdue_lines = fields.Integer(compute='_compute_summary', store=True)

    # ═══════════════════════════════════════════════════════════════════════════

    @api.depends('month', 'year')
    def _compute_name(self):
        month_names = dict(self._fields['month'].selection)
        for rec in self:
            rec.name = f"Pagos {month_names.get(rec.month, '')} {rec.year}"

    @api.depends(
        'line_ids', 'line_ids.amount_usd', 'line_ids.amount_mxn',
        'line_ids.commitment_category', 'line_ids.state', 'line_ids.tax_amount_mxn',
    )
    def _compute_summary(self):
        for rec in self:
            lines = rec.line_ids
            def _sum(cat, field):
                return sum(lines.filtered(lambda l: l.commitment_category == cat).mapped(field))

            rec.total_credit_import_usd = _sum('credit_import', 'amount_usd')
            rec.total_credit_import_mxn = _sum('credit_import', 'amount_mxn')
            rec.total_freight_sea_usd = _sum('credit_freight_sea', 'amount_usd')
            rec.total_freight_sea_mxn = _sum('credit_freight_sea', 'amount_mxn')
            rec.total_freight_land_mxn = _sum('credit_freight_land', 'amount_mxn')
            rec.total_advance_usd = _sum('advance', 'amount_usd')
            rec.total_advance_mxn = _sum('advance', 'amount_mxn')
            rec.total_balance_usd = _sum('balance', 'amount_usd')
            rec.total_balance_mxn = _sum('balance', 'amount_mxn')
            rec.total_tax_mxn = sum(lines.filtered(lambda l: l.commitment_category == 'import_tax').mapped('tax_amount_mxn'))

            rec.grand_total_usd = (
                rec.total_credit_import_usd + rec.total_freight_sea_usd +
                rec.total_advance_usd + rec.total_balance_usd
            )
            rec.grand_total_mxn = (
                rec.total_credit_import_mxn + rec.total_freight_sea_mxn +
                rec.total_freight_land_mxn + rec.total_advance_mxn +
                rec.total_balance_mxn + rec.total_tax_mxn
            )
            rec.total_lines = len(lines)
            rec.paid_lines = len(lines.filtered(lambda l: l.state == 'paid'))
            rec.pending_lines = len(lines.filtered(lambda l: l.state in ('pending', 'partial')))
            rec.overdue_lines = len(lines.filtered(lambda l: l.state == 'overdue'))

    # ═══════════════════════════════════════════════════════════════════════════

    def action_open(self):
        self.write({'state': 'open'})

    def action_close(self):
        self.write({'state': 'closed'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_populate_from_purchases(self):
        """Importar líneas desde OCs de importación con vencimientos en este mes."""
        self.ensure_one()
        month_str = f"{self.year}-{self.month}"

        schedules = self.env['purchase.payment.schedule'].search([
            ('due_date', '>=', f'{month_str}-01'),
            ('due_date', '<=', f'{month_str}-31'),
            ('order_id.is_import_order', '=', True),
        ])

        created = 0
        for sched in schedules:
            order = sched.order_id
            ref_key = f"{order.name}/{sched.id}"
            existing = self.line_ids.filtered(lambda l: l.invoice_reference == ref_key)
            if existing:
                continue

            category = 'credit_import'
            if sched.payment_type == 'advance':
                category = 'advance'
            elif sched.payment_type in ('balance', 'second_advance'):
                category = 'balance'

            type_label = dict(sched._fields['payment_type'].selection).get(sched.payment_type, '')
            self.env['import.payment.line'].create({
                'report_id': self.id,
                'name': f"{order.partner_id.name} — {order.name} ({type_label})",
                'partner_id': order.partner_id.id,
                'commitment_category': category,
                'amount_original': sched.amount,
                'currency_id': sched.currency_id.id,
                'due_date': sched.due_date,
                'invoice_reference': ref_key,
                'purchase_order_id': order.id,
                'bl_number': order.bl_number,
                'eta_date': order.eta_date,
                'state': sched.state if sched.state in ('paid', 'partial', 'overdue', 'pending') else 'pending',
                'paid_amount': sched.paid_amount,
                'paid_date': sched.paid_date,
                'note': sched.note,
                'payment_term_type': order.payment_term_id.name if order.payment_term_id else '',
            })
            created += 1

        # Impuestos de contenedores
        containers = self.env['purchase.order.container'].search([
            ('order_id.is_import_order', '=', True),
            ('order_id.eta_date', '>=', f'{month_str}-01'),
            ('order_id.eta_date', '<=', f'{month_str}-31'),
        ])
        for cont in containers:
            if not cont.tax_amount:
                continue
            existing = self.line_ids.filtered(
                lambda l: l.commitment_category == 'import_tax' and l.container_numbers == cont.name
            )
            if existing:
                continue
            order = cont.order_id
            self.env['import.payment.line'].create({
                'report_id': self.id,
                'name': f"Impuestos {cont.name} — {order.partner_id.name}",
                'partner_id': order.partner_id.id,
                'commitment_category': 'import_tax',
                'amount_original': 0,
                'currency_id': self.env.ref('base.MXN').id,
                'tax_amount_mxn': cont.tax_amount,
                'tax_is_estimate': cont.tax_state == 'pending',
                'due_date': order.eta_date,
                'eta_date': order.eta_date,
                'purchase_order_id': order.id,
                'container_numbers': cont.name,
                'state': 'paid' if cont.tax_state == 'paid' else 'pending',
                'paid_date': cont.tax_paid_date,
                'note': cont.notes,
            })
            created += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Importación completada'),
                'message': _('Se crearon %d líneas desde OCs de importación.') % created,
                'type': 'success', 'sticky': False,
            },
        }

    def action_add_line(self):
        self.ensure_one()
        return {
            'name': _('Agregar Compromiso'),
            'type': 'ir.actions.act_window',
            'res_model': 'import.payment.line.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_report_id': self.id},
        }

    # ─── RPC para el Dashboard JS ────────────────────────────────────────────

    @api.model
    def get_dashboard_data(self, report_id=False):
        """Retorna datos estructurados para el dashboard JS de Ana."""
        domain = [('report_id', '=', report_id)] if report_id else []
        lines = self.env['import.payment.line'].search_read(
            domain,
            ['name', 'partner_id', 'commitment_category', 'amount_original',
             'currency_id', 'amount_usd', 'amount_mxn', 'due_date', 'eta_date',
             'invoice_reference', 'state', 'days_until_due', 'alert_level',
             'paid_date', 'paid_amount', 'remaining_amount', 'note',
             'payment_term_type', 'bl_number', 'container_numbers',
             'sales_orders', 'tax_amount_mxn', 'tax_is_estimate',
             'target_month', 'target_month_display', 'purchase_order_id',
             'payment_programmed_date', 'report_id'],
            order='target_month, commitment_category, due_date',
        )

        # Agrupar por mes
        months = {}
        for line in lines:
            m = line.get('target_month') or 'sin_fecha'
            if m not in months:
                months[m] = {
                    'display': line.get('target_month_display', 'Sin Fecha'),
                    'lines': [],
                    'summary': {
                        'credit_import_usd': 0, 'credit_import_mxn': 0,
                        'freight_sea_usd': 0, 'freight_sea_mxn': 0,
                        'freight_land_mxn': 0,
                        'advance_usd': 0, 'advance_mxn': 0,
                        'balance_usd': 0, 'balance_mxn': 0,
                        'tax_mxn': 0,
                        'total_usd': 0, 'total_mxn': 0,
                        'paid': 0, 'pending': 0, 'overdue': 0, 'total': 0,
                    }
                }
            months[m]['lines'].append(line)
            s = months[m]['summary']
            cat = line.get('commitment_category', '')
            usd = line.get('amount_usd', 0) or 0
            mxn = line.get('amount_mxn', 0) or 0
            tax = line.get('tax_amount_mxn', 0) or 0

            if cat == 'credit_import':
                s['credit_import_usd'] += usd
                s['credit_import_mxn'] += mxn
            elif cat == 'credit_freight_sea':
                s['freight_sea_usd'] += usd
                s['freight_sea_mxn'] += mxn
            elif cat == 'credit_freight_land':
                s['freight_land_mxn'] += mxn
            elif cat == 'advance':
                s['advance_usd'] += usd
                s['advance_mxn'] += mxn
            elif cat == 'balance':
                s['balance_usd'] += usd
                s['balance_mxn'] += mxn
            elif cat == 'import_tax':
                s['tax_mxn'] += tax

            s['total'] += 1
            st = line.get('state', '')
            if st == 'paid':
                s['paid'] += 1
            elif st == 'overdue':
                s['overdue'] += 1
            else:
                s['pending'] += 1

        # Calcular grand totals por mes
        for m in months.values():
            s = m['summary']
            s['total_usd'] = s['credit_import_usd'] + s['freight_sea_usd'] + s['advance_usd'] + s['balance_usd']
            s['total_mxn'] = (
                s['credit_import_mxn'] + s['freight_sea_mxn'] + s['freight_land_mxn'] +
                s['advance_mxn'] + s['balance_mxn'] + s['tax_mxn']
            )

        # Reportes disponibles
        reports = self.search_read([], ['name', 'month', 'year', 'state'], order='year desc, month desc')

        return {
            'months': months,
            'reports': reports,
        }
