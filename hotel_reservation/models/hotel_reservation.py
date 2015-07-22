# -*- encoding: utf-8 -*-
##############################################################################
#    
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.     
#
##############################################################################

from openerp import models
from openerp import fields
from openerp import api
from openerp import pooler
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
                                 #required=True,
                                 select=True,
                                 readonly=True)
                                 
    date_order = fields.Datetime('Date Ordered',
                                 #required=True,
                                 readonly=True,
                                 states={'draft':[('readonly',False)]},
                                 default = (lambda *a: time.strftime('%Y-%m-%d %H:%M:%S')))
                                 
    hotel_id = fields.Many2one('stock.warehouse',
                              string='Hotel',
                              #required=True,
                              readonly=True,
                              states={'draft':[('readonly',False)]},
                              default=1)  
                                 
    partner_id = fields.Many2one('res.partner',
                                 string='Guest Name',
                                 #required=True,
                                 readonly=True,
                                 states={'draft':[('readonly',False)]},
                                 default=1)
                                 
    pricelist_id = fields.Many2one('product.pricelist',
                                   string='Pricelist',
                                   #required=True,
                                   readonly=True,
                                   states={'draft':[('readonly',False)]})
                                   
    partner_invoice_id = fields.Many2one('res.partner.address',
                                         string="Invoice Address",
                                         readonly=True,
                                         #required=True,
                                         states={'draft':[('readonly',False)]})
                                         
    partner_order_id = fields.Many2one('res.partner.address',
                                       string='Ordering Contact',
                                       readonly=True,
                                       #required=True,
                                       states={'draft':[('readonly',False)]},
                                       help="The name and address of the contact \
                                        that requested the order or quotation.")
                                        
    partner_shipping_id = fields.Many2one('res.partner.address',
                                          string='Shipping Address',
                                          readonly=True,
                                          #required=True,
                                          states={'draft':[('readonly',False)]})
                                          
    checkin = fields.Datetime('Expected-Date-Arrival',
                               #required=True,
                               readonly=True,
                               states={'draft':[('readonly',False)]})
                               
    checkout = fields.Datetime('Expected-Date-Departure',
                                #required=True,
                                readonly=True,
                                states={'draft':[('readonly',False)]})
                                
    adults = fields.Integer('Adults',
                            size=64,
                            readonly=True,
                            states={'draft':[('readonly',False)]})
                            
    childs = fields.Integer('Children',
                            size=64,
                            readonly=True,
                            states={'draft':[('readonly',False)]})   
                                     
    reservation_line = fields.One2many('hotel_reservation.line',
                                       'line_id',
                                       'Reservation Line')
                                       
    state = fields.Selection([('draft', 'Draft'),
                              ('confirm','Confirm'),
                              ('cancle','Cancle'),
                              ('done','Done')],
                              string='State',
                              readonly=True,
                              default = (lambda *a: 'draft'))
                              
    folio_id = fields.Many2many('hotel.folio',
                                'hotel_folio_reservation_rel',
                                'order_id',
                                'invoice_id',
                                'Folio')
                                
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
        #alternative
        self.partner_invoice_id = self.partner_id.id
        self.partner_order_id = self.partner_id.id
        self.partner_shipping_id = self.partner_id.id
        self.pricelist_id = self.partner_id.property_product_pricelist.id
        
    @api.multi 
    def confirmed_reservation(self):
         
        for reservation in self.browse():
            cr.execute("select count(*) from hotel_reservation as hr " \
                        "inner join hotel_reservation_line as hrl on hrl.line_id = hr.id " \
                        "inner join hotel_reservation_line_room_rel as hrlrr on hrlrr.room_id = hrl.id " \
                        "where (checkin,checkout) overlaps ( timestamp %s , timestamp %s ) " \
                        "and hr.id <> cast(%s as integer) " \
                        "and hr.state = 'confirm' " \
                        "and hrlrr.hotel_reservation_line_id in (" \
                        "select hrlrr.hotel_reservation_line_id from hotel_reservation as hr " \
                        "inner join hotel_reservation_line as hrl on hrl.line_id = hr.id " \
                        "inner join hotel_reservation_line_room_rel as hrlrr on hrlrr.room_id = hrl.id " \
                        "where hr.id = cast(%s as integer) )" \
                        ,(reservation.checkin,reservation.checkout,str(reservation.id),str(reservation.id)))
            
            res = cr.fetchone()
            roomcount =  res and res[0] or 0.0
            if roomcount:
                raise Warning('Warning', 'You tried to confirm reservation \
                 with room those already reserved in this reservation period')
            else:
                 
                self.write({'state':'confirm'})
            return True
    
    @api.model
    def create(self, field):
        field['reservation_no'] = self.env['ir.sequence'].get('hotel.reservation')
        res = super(hotel_reservation, self).create(field)
        return res
    
    @api.multi
    def create_folio(self):
        for reservation in self.browse():
            for line in reservation.reservation_line:
                 for r in line.reserve:
                    folio=self.env['hotel.folio'].create({'date_order':reservation.date_order,
                                                          'hotel_id':reservation.warehouse_id.id,
                                                          'partner_id':reservation.partner_id.id,
                                                          'pricelist_id':reservation.pricelist_id.id,
                                                          'partner_invoice_id':reservation.partner_invoice_id.id,
                                                          'partner_order_id':reservation.partner_order_id.id,
                                                          'partner_shipping_id':reservation.partner_shipping_id.id,
                                                          'checkin_date': reservation.checkin,
                                                          'checkout_date': reservation.checkout,
                                                          'room_lines': [(0,0,{'folio_id':line['id'],
                                                                               'checkin_date':reservation['checkin'],
                                                                               'checkout_date':reservation['checkout'],
                                                                               'product_id':r['id'], 
                                                                               'name':reservation['reservation_no'],
                                                                               'product_uom':r['uom_id'].id,
                                                                               'price_unit':r['lst_price'],
                                                                               'product_uom_qty':(datetime.datetime(*time.strptime(reservation['checkout'],'%Y-%m-%d %H:%M:%S')[:5]) - datetime.datetime(*time.strptime(reservation['checkin'],'%Y-%m-%d %H:%M:%S')[:5])).days   
                                                                               
                                                                               })],
                                                         'service_lines':reservation['folio_id']     
                                                         })
            cr.execute('insert into hotel_folio_reservation_rel (order_id,invoice_id) values (%s,%s)', (reservation.id, folio))
            self.write({'state':'done'})
        return True

class hotel_reservation_line(models.Model):
    
     _name = 'hotel_reservation.line'
     _description = 'Reservation Line'
     
     line_id = fields.Many2one('hotel.reservation')
     
     reserve = fields.Many2many('product.product',
                                'hotel_reservation_line_room_rel',
                                'room_id',
                                'hotel_reservation_line_id',
                                domain="[('isroom','=',True),\
                                ('categ_id','=',categ_id)]")  
      
     categ_id = fields.Many2one('product.category',
                               'Room Type',
                               domain="[('isroomtype','=',True)]")






# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:


