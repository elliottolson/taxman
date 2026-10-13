from fractions import Fraction
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from exact_numbers import Exact,parse,arithmetic,quantize,render,round_line_total
from validate_model import ModelError


class ExactNumberTests(unittest.TestCase):
    def test_decimal_inputs_are_exact(self):
        self.assertEqual(parse('Rate','0.1').amount,Fraction(1,10))
        self.assertEqual(parse('Decimal','0.12345678901234567890123456789').amount,Fraction(12345678901234567890123456789,10**29))

    def test_float_and_bool_coercions_are_rejected(self):
        for typ,value in [('Money',1.0),('Rate',0.1),('Integer',True),('Integer',1.0)]:
            with self.assertRaises(ModelError):parse(typ,value)

    def test_money_requires_cents_not_exponents(self):
        for value in ['1','1.0','1.000','1e2','NaN','Infinity','01.00']:
            with self.assertRaises(ModelError):parse('Money',value)

    def test_exact_addition_does_not_accumulate_binary_error(self):
        self.assertEqual(render(arithmetic('add',[parse('Money','0.10'),parse('Money','0.20')])),'0.30')

    def test_rate_product_retains_fractional_cents(self):
        result=arithmetic('multiply',[parse('Money','0.01'),parse('Rate','0.5')])
        self.assertEqual(result.amount,Fraction(1,200))
        with self.assertRaisesRegex(ModelError,'explicit rounding'):render(result)
        self.assertEqual(render(result,2,'half_up'),'0.01')
        self.assertEqual(render(result,2,'half_even'),'0.00')

    def test_nonterminating_division_is_exact(self):
        result=arithmetic('divide',[parse('Money','1.00'),parse('Integer',3)])
        self.assertEqual(result.amount,Fraction(1,3))
        self.assertEqual(render(result,2,'half_up'),'0.33')

    def test_money_ratio_has_rate_units(self):
        result=arithmetic('divide',[parse('Money','1.00'),parse('Money','3.00')])
        self.assertEqual((result.value_type,result.amount),('Rate',Fraction(1,3)))

    def test_incompatible_dimensions_are_rejected(self):
        for op,values in [('multiply',[parse('Money','1.00'),parse('Money','2.00')]),('divide',[parse('Rate','0.5'),parse('Money','1.00')]),('add',[parse('Money','1.00'),parse('Rate','0.1')])]:
            with self.assertRaises(ModelError):arithmetic(op,values)

    def test_division_by_zero(self):
        with self.assertRaisesRegex(ModelError,'Division by zero'):
            arithmetic('divide',[parse('Money','1.00'),parse('Integer',0)])

    def test_half_up_and_half_even_ties_are_explicit(self):
        self.assertEqual(render(parse('Money','2.50'),0,'half_up'),'3')
        self.assertEqual(render(parse('Money','2.50'),0,'half_even'),'2')
        self.assertEqual(render(parse('Money','3.50'),0,'half_even'),'4')
        self.assertEqual(render(parse('Money','-2.50'),0,'half_up'),'-3')

    def test_floor_ceiling_and_truncate_differ_for_negative_values(self):
        v=parse('Money','-1.99')
        self.assertEqual(render(v,0,'floor'),'-2')
        self.assertEqual(render(v,0,'ceiling'),'-1')
        self.assertEqual(render(v,0,'truncate'),'-1')

    def test_negative_zero_is_canonical(self):
        self.assertEqual(render(parse('Money','-0.00')),'0.00')
        self.assertEqual(render(parse('Money','-0.01'),0,'truncate'),'0')

    def test_irs_published_rounding_examples(self):
        self.assertEqual(round_line_total([parse('Money','1.39')]),'1')
        self.assertEqual(round_line_total([parse('Money','2.50')]),'3')

    def test_line_components_are_summed_before_rounding(self):
        values=[parse('Money','1.49'),parse('Money','1.49')]
        self.assertEqual(round_line_total(values),'3')
        self.assertEqual(sum(int(round_line_total([v])) for v in values),2)

    def test_unsigned_irs_rounding_policy_does_not_invent_negative_convention(self):
        with self.assertRaisesRegex(ModelError,'nonnegative'):round_line_total([parse('Money','-1.50')])

    def test_rounding_policy_is_required_for_lost_precision(self):
        with self.assertRaises(ModelError):quantize(parse('Money','1.50'),0,'exact')
        with self.assertRaises(ModelError):quantize(parse('Money','1.50'),0,'unknown')

    def test_large_values_do_not_depend_on_decimal_context(self):
        a=parse('Money','999999999999999999999999999999.99')
        self.assertEqual(render(arithmetic('add',[a,parse('Money','0.01')])),'1000000000000000000000000000000.00')

    def test_integer_operations_preserve_integrality(self):
        r=arithmetic('multiply',[parse('Integer',2),parse('Integer',3)])
        self.assertEqual((r.value_type,r.amount),('Integer',Fraction(6)))
        with self.assertRaises(ModelError):Exact('Integer',Fraction(1,2))


if __name__=='__main__':unittest.main()
