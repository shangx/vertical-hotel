# -*- encoding: utf-8 -*-

from openerp import models
from openerp import fields
from openerp import api
from openerp import pooler
from openerp import tools
from openerp.tools.translate import _
from openerp import exceptions
from openerp.exceptions import Warning
from openerp.tools import config
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
import time
import datetime


class hotel_reservation(models.Model):
    _name = 'hotel.reservation'
    _rec_name = 'reservation_no'
    _description = 'Reservation'

    reservation_no = fields.Char('Reservation No',
                                 size=64,
                                 required=True,
                                 select=True,
                                 readonly=True,
                                 default='/')

    date_order = fields.Datetime('Date Ordered',
                                 required=True,
                                 readonly=True,
                                 states={'draft': [('readonly', False)]},
                                 default=(lambda *a:
                                          time.strftime('%Y-%m-%d %H:%M:%S')))

    hotel_id = fields.Many2one('stock.warehouse',
                               string='Hotel',
                               required=True,
                               readonly=True,
                               states={'draft': [('readonly', False)]},
                               default=1)

    partner_id = fields.Many2one('res.partner',
                                 string='Guest Name',
                                 required=True,
                                 readonly=True,
                                 states={'draft': [('readonly', False)]},
                                 default=1)

    pricelist_id = fields.Many2one('product.pricelist',
                                   string='Pricelist',
                                   required=True,
                                   readonly=True,
                                   states={'draft': [('readonly', False)]})

    partner_invoice_id = fields.Many2one('res.partner',
                                         string="Invoice Address",
                                         readonly=True,
                                         required=True,
                                         states={'draft': [('readonly',
                                                            False)]})

    partner_order_id = fields.Many2one('res.partner',
                                       string='Ordering Contact',
                                       readonly=True,
                                       required=True,
                                       states={'draft': [('readonly', False)]},
                                       help="The name and address of the contact \
                                        that requested the order or quotation")

    partner_shipping_id = fields.Many2one('res.partner',
                                          string='Shipping Address',
                                          readonly=True,
                                          required=True,
                                          states={'draft': [('readonly',
                                                             False)]})

    checkin = fields.Datetime('Expected-Date-Arrival',
                              required=True,
                              readonly=True,
                              states={'draft': [('readonly', False)]})

    checkout = fields.Datetime('Expected-Date-Departure',
                               required=True,
                               readonly=True,
                               states={'draft': [('readonly', False)]})

    adults = fields.Integer('Adults',
                            size=64,
                            readonly=True,
                            states={'draft': [('readonly', False)]})

    childs = fields.Integer('Children',
                            size=64,
                            readonly=True,
                            states={'draft': [('readonly', False)]})

    reservation_line = fields.One2many('hotel_reservation.line',
                                       'line_id',
                                       'Reservation Line')

    state = fields.Selection([('draft', 'Draft'),
                              ('confirm', 'Confirm'),
                              ('cancle', 'Cancle'),
                              ('done', 'Done')],
                             string='State',
                             readonly=True,
                             default=(lambda *a: 'draft'))

    folio_id = fields.Many2many('hotel.folio',
                                'hotel_folio_reservation_rel',
                                'order_id',
                                'invoice_id',
                                'Folio')

    order_line_id = fields.Many2one(
        'sale.order.line',
        string='Order Line',
        required=True,
        ondelete='cascade',
        delegate=True)

    dummy = fields.Datetime('Dummy')

    '''
    @api.multi
    @api.onchange('checkout_date','checkin_date')
    def on_change_checkout(self,):

        checkin_date=time.strftime('%Y-%m-%d %H:%M:%S')
        checkout_date=time.strftime('%Y-%m-%d %H:%M:%S')

        delta = datetime.timedelta(days=1)

        addDays = datetime.datetime(*time.strptime(checkout_date, \
                                                   '%Y-%m-%d %H:%M:%S')[:5]) \
                                                    + delta

        self.dummy = addDays.strftime('%Y-%m-%d %H:%M:%S')
    '''

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        '''
        if not self.partner_id:
            raise Warning('Invalid partner ID')
        else:
            addr = self.partner_id.address_get(['delivery','invoice','contact'])
            self.partner_invoice_id = addr['invoice']
            self.partner_order_id = addr['contact']
            self.partner_shipping_id = addr['delivery']
            self.pricelist_id = self.partner_id.property_product_pricelist.id
        '''
        # alternative
        self.partner_invoice_id = self.partner_id.id
        self.partner_order_id = self.partner_id.id
        self.partner_shipping_id = self.partner_id.id
        self.pricelist_id = self.partner_id.property_product_pricelist.id

    @api.multi
    def confirmed_reservation(self):

        for reservation in self.browse(self.ids):
            self._cr.execute("""select count(*) from hotel_reservation as hr
                        inner join hotel_reservation_line
                        as hrl on hrl.line_id=hr.id
                        inner join hotel_reservation_line_room_rel
                        as hrlrr on hrlrr.id = hrl.id
                        where (checkin,checkout)
                        overlaps ( timestamp %s , timestamp %s )
                        and hr.id <> cast(%s as integer)
                        and hr.state = 'confirm'
                        and hrlrr.hotel_reservation_line_id in (
                        select hrlrr.hotel_reservation_line_id
                        from hotel_reservation as hr
                        inner join hotel_reservation_line
                        as hrl on hrl.line_id = hr.id
                        inner join hotel_reservation_line_room_rel
                        as hrlrr on hrlrr.id = hrl.id
                        where hr.id = cast(%s as integer) )""",
                             (reservation.checkin,
                              reservation.checkout,
                              str(reservation.id), str(reservation.id)))

            res = self._cr.fetchone()
            roomcount = res and res[0] or 0.0
            if roomcount:
                raise Warning('Warning', 'You tried to confirm reservation \
                 with room those already reserved in this reservation period')
            else:

                self.write({'state': 'confirm'})
        return True

    @api.model
    def create(self, field):
        field['reservation_no'] = self.env['ir.sequence'].get('hotel.reservation')
        res = super(hotel_reservation, self).create(field)
        return res

    @api.multi
    def create_folio(self):
        for reservation in self.browse(self.ids):
            for line in reservation.reservation_line:
                for r in line.reserve:
                    folio = self.env['hotel.folio'].create(
                         {'date_order': reservation.date_order,
                          'partner_id': reservation.partner_id.id,
                          'pricelist_id': reservation.pricelist_id.id,
                          'partner_invoice_id':
                          reservation.partner_invoice_id.id,
                          'partner_order_id':
                          reservation.partner_order_id.id,
                          'partner_shipping_id':
                          reservation.partner_shipping_id.id,
                          'checkin_date': reservation.checkin,
                          'checkout_date': reservation.checkout,
                          'duration': (datetime.datetime(*time.strptime(reservation['checkout'],'%Y-%m-%d %H:%M:%S')[:5]) - datetime.datetime(*time.strptime(reservation['checkin'],'%Y-%m-%d %H:%M:%S')[:5])).days
                          })
                    self._cr.execute('insert into hotel_folio_reservation_rel (order_id,invoice_id) values (%s,%s)', (reservation.id, folio.id))
                    room_line = self.env['hotel.folio.room'].create(
                        {'folio_id': folio.id,
                         'name': r.name_template,
                         'product_id': r.id,
                         'product_uom': r['uom_id'].id,
                         'price_unit': r['lst_price'],
                         'order_line_id': order_line_id,
                         'checkin_date': reservation['checkin'],
                         'checkout_date': reservation['checkout'],
                         })
                         #'service_lines':reservation['folio_id']
            self.write({'state':'done'})
        return True


class hotel_reservation_line(models.Model):

    _name = 'hotel_reservation.line'
    _description = 'Reservation Line'

    line_id = fields.Many2one('hotel.reservation',
                              delegate=True)

    reserve = fields.Many2many('product.product',
                               'hotel_reservation_line_room_rel',
                               'hotel_reservation_line_id',
                               'id',
                               delegate=True,
                               domain="[('isroom', '=', True),]")

    categ_id = fields.Many2one('product.category',
                               'Room Type',
                               delegate=True,
                               domain="[('isroomtype','=',True)]")
