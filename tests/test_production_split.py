#!/usr/bin/env python
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from decimal import Decimal
import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, test_view,\
    test_depends
from trytond.transaction import Transaction


class ProductionSplitTestCase(unittest.TestCase):
    'Test production_split module'

    def setUp(self):
        trytond.tests.test_tryton.install_module('production_split')
        self.uom = POOL.get('product.uom')
        self.template = POOL.get('product.template')
        self.product = POOL.get('product.product')
        self.production = POOL.get('production')
        self.bom = POOL.get('production.bom')
        self.location = POOL.get('stock.location')
        self.company = POOL.get('company.company')
        self.user = POOL.get('res.user')
        self.move = POOL.get('stock.move')
        self.inventory = POOL.get('stock.inventory')

    def test0005views(self):
        'Test views'
        test_view('production_split')

    def test0006depends(self):
        'Test depends'
        test_depends()

    def test0010split(self):
        'Test split production'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            input_, = self.location.search([('code', '=', 'IN')])
            storage, = self.location.search([('code', '=', 'STO')])
            production_loc, = self.location.search([('code', '=', 'PROD')])
            warehouse, = self.location.search([('code', '=', 'WH')])
            warehouse.production_location = production_loc
            warehouse.save()

            company, = self.company.search([
                    ('rec_name', '=', 'Dunder Mifflin'),
                    ])
            self.user.write([self.user(USER)], {
                    'main_company': company.id,
                    'company': company.id,
                    })

            unit, = self.uom.search([('name', '=', 'Unit')])
            box5 = self.uom(
                name='Box of 5',
                symbol='b5',
                category=unit.category,
                factor=5,
                rate=0.2,
                rounding=1,
                digits=0)
            box5.save()

            template, = self.template.create([{
                        'name': 'Product',
                        'type': 'goods',
                        'cost_price_method': 'fixed',
                        'default_uom': unit.id,
                        'list_price': Decimal(5),
                        'cost_price': Decimal(1),
                        }])
            product, = self.product.create([{
                        'template': template.id,
                        }])
            template1, = self.template.create([{
                        'name': 'Component 1',
                        'type': 'goods',
                        'cost_price_method': 'fixed',
                        'default_uom': unit.id,
                        'list_price': Decimal(5),
                        'cost_price': Decimal(1),
                        }])
            component1, = self.product.create([{
                        'template': template1.id,
                        }])
            template2, = self.template.create([{
                        'name': 'Component 2',
                        'type': 'goods',
                        'cost_price_method': 'fixed',
                        'default_uom': unit.id,
                        'list_price': Decimal(5),
                        'cost_price': Decimal(2),
                        }])
            component2, = self.product.create([{
                        'template': template2.id,
                        }])

            bom, = self.bom.create([{
                        'name': 'Product',
                        'inputs': [('create', [{
                                        'product': component1.id,
                                        'quantity': 5.0,
                                        'uom': unit.id,
                                        }, {
                                        'product': component2.id,
                                        'quantity': 2.0,
                                        'uom': unit.id,
                                        }])],
                        'outputs': [('create', [{
                                        'product': product.id,
                                        'quantity': 1.0,
                                        'uom': unit.id,
                                        }])],
                        }])

            def create_production(quantity):
                production, = self.production.create([{
                            'product': product.id,
                            'bom': bom.id,
                            'uom': unit.id,
                            'quantity': quantity,
                            'warehouse': warehouse.id,
                            'location': production_loc.id,
                            'company': company.id,
                            }])
                production.set_moves()
                return production

            production = create_production(10)
            self.assertEqual(production.code, '1')
            productions = production.split(5, unit)
            self.assertEqual(len(productions), 2)
            self.assertEqual([p.code for p in productions], ['1-1', '1-2'])
            self.assertEqual([m.quantity for m in productions], [5, 5])
            self.assertEqual([sorted([m.quantity for m in p.inputs]) for p in
                    productions], [[10, 25], [10, 25]])
            self.assertEqual([[m.quantity for m in p.outputs] for p in
                    productions], [[5], [5]])

            production = create_production(13)
            productions = production.split(5, unit)
            self.assertEqual(len(productions), 3)
            self.assertEqual([m.quantity for m in productions], [5, 5, 3])
            self.assertEqual([sorted([m.quantity for m in p.inputs]) for p in
                    productions], [[10, 25], [10, 25], [6, 15]])
            self.assertEqual([[m.quantity for m in p.outputs] for p in
                    productions], [[5], [5], [3]])

            production = create_production(7)
            productions = production.split(8, unit)
            self.assertEqual(productions, [production])
            self.assertEqual(production.quantity, 7)
            self.assertEqual(sorted([m.quantity for m in production.inputs]),
                [14, 35])
            self.assertEqual([m.quantity for m in production.outputs], [7])

            production = create_production(20)
            productions = production.split(5, unit, count=2)
            self.assertEqual(len(productions), 3)
            self.assertEqual([m.quantity for m in productions], [5, 5, 10])
            self.assertEqual([sorted([m.quantity for m in p.inputs]) for p in
                    productions], [[10, 25], [10, 25], [20, 50]])
            self.assertEqual([[m.quantity for m in p.outputs] for p in
                    productions], [[5], [5], [10]])

            production = create_production(20)
            productions = production.split(5, unit, count=4)
            self.assertEqual(len(productions), 4)
            self.assertEqual([m.quantity for m in productions], [5, 5, 5, 5])
            self.assertEqual([sorted([m.quantity for m in p.inputs]) for p in
                    productions], [[10, 25], [10, 25], [10, 25], [10, 25]])
            self.assertEqual([[m.quantity for m in p.outputs] for p in
                    productions], [[5], [5], [5], [5]])

            production = create_production(10)
            productions = production.split(5, unit, count=3)
            self.assertEqual(len(productions), 2)
            self.assertEqual([m.quantity for m in productions], [5, 5])
            self.assertEqual([sorted([m.quantity for m in p.inputs]) for p in
                    productions], [[10, 25], [10, 25]])
            self.assertEqual([[m.quantity for m in p.outputs] for p in
                    productions], [[5], [5]])

            # Productions with two moves for the same input with different UoM
            complex_production = create_production(20)
            component1_move, = [m for m in complex_production.inputs
                if m.product == component1]
            self.assertEqual(component1_move.quantity, 100)
            component1_move2, = self.move.copy([component1_move], {
                    'quantity': 10,
                    'uom': box5.id,
                    })
            component1_move.quantity = 50
            component1_move.save()

            production, = self.production.copy([complex_production])
            # split in 2 equal productions: input moves are not splitted
            productions = production.split(10, unit)
            self.assertEqual(len(productions), 2)
            self.assertEqual([m.quantity for m in productions], [10, 10])
            self.assertEqual(sorted([sorted([(m.quantity, m.uom.symbol)
                                for m in p.inputs]) for p in productions]),
                [[(10, u'b5'), (20, u'u')], [(20, u'u'), (50, u'u')]])
            self.assertEqual([[m.quantity for m in p.outputs] for p in
                    productions], [[10], [10]])

            production, = self.production.copy([complex_production])
            # split in 4 equal productions: input moves splitted
            productions = production.split(5, unit)
            self.assertEqual(len(productions), 4)
            self.assertEqual([m.quantity for m in productions], [5, 5, 5, 5])
            self.assertEqual(sorted([sorted([(m.quantity, m.uom.symbol)
                                for m in p.inputs]) for p in productions]),
                [[(5, u'b5'), (10, u'u')], [(5, u'b5'), (10, u'u')],
                    [(10, u'u'), (25, u'u')], [(10, u'u'), (25, u'u')]])
            self.assertEqual([[m.quantity for m in p.outputs] for p in
                    productions], [[5], [5], [5], [5]])

            production, = self.production.copy([complex_production])
            # split in 3 NON equal productions: input moves splitted
            productions = production.split(5, unit, count=2)
            self.assertEqual(len(productions), 3)
            res = sorted([(p.quantity, sorted([(m.quantity, m.uom.symbol)
                                for m in p.inputs])) for p in productions])
            try:
                self.assertEqual(res, [
                        (5, [(5, u'b5'), (10, u'u')]),
                        (5, [(5, u'b5'), (10, u'u')]),
                        (10, [(20, u'u'), (50, u'u')]),
                        ])
            except AssertionError:
                # We can not supose how will be exactly splitted
                self.assertEqual(res, [
                        (5, [(10, u'u'), (25, u'u')]),
                        (5, [(10, u'u'), (25, u'u')]),
                        (10, [(10, u'b5'), (20, u'u')]),
                        ])
            self.assertEqual([(p.quantity, [m.quantity for m in p.outputs])
                    for p in productions],
                [(5, [5]), (5, [5]), (10, [10])])

            production, = self.production.copy([complex_production])
            # split in 3 NON equal productions and different production UoM
            productions = production.split(1, box5, count=2)
            self.assertEqual(len(productions), 3)
            res = sorted([(p.quantity, sorted([(m.quantity, m.uom.symbol)
                                for m in p.inputs])) for p in productions])
            try:
                self.assertEqual(res, [
                        (1, [(5, u'b5'), (10, u'u')]),
                        (2, [(5, u'b5'), (10, u'u')]),
                        (2, [(20, u'u'), (50, u'u')]),
                        ])
            except AssertionError:
                # We can not supose how will be exactly splitted
                self.assertEqual(res, [
                        (1, [(10, u'u'), (25, u'u')]),
                        (1, [(10, u'u'), (25, u'u')]),
                        (2, [(10, u'b5'), (20, u'u')]),
                        ])

            # Split in non draft state
            production = create_production(10)
            self.production.wait([production])
            productions = production.split(5, unit)
            self.assertEqual(len(productions), 2)
            self.assertEqual([p.quantity for p in productions], [5, 5])
            self.assertEqual([p.state for p in productions],
                ['waiting', 'waiting'])

            inventory, = self.inventory.create([{
                        'company': company.id,
                        'location': storage.id,
                        'lines': [('create', [{
                                        'product': component1.id,
                                        'quantity': 50,
                                        }, {
                                        'product': component2.id,
                                        'quantity': 20,
                                        }])],
                        }])
            self.inventory.confirm([inventory])

            production = create_production(10)
            self.production.wait([production])
            self.assertEqual(self.production.assign_try([production]), True)
            productions = production.split(5, unit)
            self.assertEqual(len(productions), 2)
            self.assertEqual([m.quantity for m in productions], [5, 5])
            self.assertEqual([m.state for m in productions],
                ['assigned', 'assigned'])
            self.assertEqual([sorted([m.quantity for m in p.inputs]) for p in
                    productions], [[10, 25], [10, 25]])
            self.assertEqual([[m.quantity for m in p.outputs] for p in
                    productions], [[5], [5]])
            self.assertEqual(all([m.state == 'draft' for m in p.outputs
                        for p in productions]), True)

            production = create_production(10)
            production.bom == None
            production.product == None
            production.save()
            productions = production.split(5, unit)
            self.assertEqual(len(productions), 2)
            self.assertEqual([sorted([m.quantity for m in p.inputs]) for p in
                    productions], [[10, 25], [10, 25]])
            self.assertEqual([[m.quantity for m in p.outputs] for p in
                    productions], [[5], [5]])
            production = create_production(10)
            production.product == None
            production.save()

            production = create_production(10)
            self.production.write([production], {
                    'bom': None,
                    'outputs': [('create', [{
                                    'product': component2.id,
                                    'uom': unit.id,
                                    'quantity': 2,
                                    'from_location': production_loc.id,
                                    'to_location': storage.id,
                                    'company': company.id,
                                    'currency': company.currency.id,
                                    'unit_price': component2.cost_price,
                                    },
                                ])]
                    })
            self.assertEqual(len(production.outputs), 2)
            productions = production.split(5, unit)
            self.assertEqual(len(productions), 2)
            self.assertEqual([sorted([m.quantity for m in p.inputs]) for p in
                    productions], [[10, 25], [10, 25]])
            self.assertEqual([sorted([m.quantity for m in p.outputs]) for p in
                    productions], [[1, 5], [1, 5]])


def suite():
    suite = trytond.tests.test_tryton.suite()
    from trytond.modules.company.tests import test_company
    for test in test_company.suite():
        if test not in suite:
            suite.addTest(test)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            ProductionSplitTestCase))
    return suite
