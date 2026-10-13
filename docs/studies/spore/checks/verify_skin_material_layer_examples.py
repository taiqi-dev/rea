"""Independent material-channel composition; not original-game blend formulas."""
from dataclasses import dataclass
import math
import unittest


@dataclass(frozen=True)
class Material:
    color: tuple
    height_m: float
    specular: float


@dataclass(frozen=True)
class Brush:
    coverage: float
    color: tuple | None = None
    color_alpha: float = 0
    height_delta_m: float | None = None
    height_alpha: float = 0
    specular_target: float | None = None
    specular_alpha: float = 0


def apply(material, brush):
    alphas=(brush.coverage,brush.color_alpha,brush.height_alpha,brush.specular_alpha)
    if not all(math.isfinite(a) and 0<=a<=1 for a in alphas):
        raise ValueError('InvalidBrushAlpha')
    if brush.color is not None and (len(brush.color)!=3 or not all(math.isfinite(v) and 0<=v<=1 for v in brush.color)):
        raise ValueError('InvalidLinearColor')
    if brush.height_delta_m is not None and not math.isfinite(brush.height_delta_m):
        raise ValueError('InvalidHeight')
    if brush.specular_target is not None and not (math.isfinite(brush.specular_target) and 0<=brush.specular_target<=1):
        raise ValueError('InvalidSpecular')
    ca=brush.coverage*brush.color_alpha
    ha=brush.coverage*brush.height_alpha
    sa=brush.coverage*brush.specular_alpha
    color=material.color if brush.color is None else tuple((1-ca)*a+ca*b for a,b in zip(material.color,brush.color))
    height=material.height_m+(0 if brush.height_delta_m is None else ha*brush.height_delta_m)
    specular=material.specular if brush.specular_target is None else (1-sa)*material.specular+sa*brush.specular_target
    return Material(color,height,specular)


def example():
    base=Material((.2,.4,.6),.0002,.3)
    coat=apply(base,Brush(.8,(.8,.2,.1),.5,.001,.5,.8,.5))
    detail=apply(coat,Brush(.5,(.05,.05,.05),.25,-.0005,.25))
    # Separate declared detail specular operation: attenuate toward factor .7.
    detail=Material(detail.color,detail.height_m,detail.specular*(1+.125*(.7-1)))
    return base,coat,detail


def resolve_layers(ids, registry):
    if len(ids)!=3:
        raise ValueError('OwnThemeRequiresThreeSlots')
    result=[]
    for slot, ident in zip(('Base','Coat','Detail'),ids):
        if ident is None:
            result.append((slot,None))
        elif ident not in registry:
            raise ValueError(f'UnknownPaintLayer:{slot}:{ident}')
        else:
            result.append((slot,registry[ident]))
    return result


class MaterialExamples(unittest.TestCase):
    def test_complete_color_example(self):
        _,coat,detail=example()
        for actual,expected in zip(coat.color,(.44,.32,.40)):
            self.assertAlmostEqual(actual,expected)
        for actual,expected in zip(detail.color,(.39125,.28625,.35625)):
            self.assertAlmostEqual(actual,expected)

    def test_height_has_independent_meter_units(self):
        _,coat,detail=example()
        self.assertAlmostEqual(coat.height_m,.0006)
        self.assertAlmostEqual(detail.height_m,.0005375)
        self.assertAlmostEqual(detail.height_m*1000,.5375)

    def test_specular_is_not_color_or_height_blend(self):
        _,coat,detail=example()
        self.assertAlmostEqual(coat.specular,.5)
        self.assertAlmostEqual(detail.specular,.48125)

    def test_specular_only_brush_does_not_repaint_color(self):
        base=Material((.2,.4,.6),.001,.2)
        wet=apply(base,Brush(1,specular_target=.9,specular_alpha=.5))
        self.assertEqual(wet.color,base.color)
        self.assertEqual(wet.height_m,base.height_m)
        self.assertAlmostEqual(wet.specular,.55)

    def test_height_only_brush_does_not_change_specular(self):
        base=Material((.2,.4,.6),.001,.2)
        bumped=apply(base,Brush(.5,height_delta_m=.002,height_alpha=1))
        self.assertEqual(bumped.color,base.color)
        self.assertEqual(bumped.specular,base.specular)
        self.assertAlmostEqual(bumped.height_m,.002)

    def test_zero_coverage_preserves_all_channels(self):
        base=example()[0]
        self.assertEqual(apply(base,Brush(0,(1,0,0),1,.1,1,1,1)),base)

    def test_masks_and_alpha_are_multiplied_not_added(self):
        base=Material((0,0,0),0,0)
        painted=apply(base,Brush(.5,(1,1,1),.2))
        self.assertEqual(painted.color,(.1,.1,.1))

    def test_invalid_brush_preserves_immutable_prior_material(self):
        base=example()[0]
        with self.assertRaisesRegex(ValueError,'InvalidHeight'):
            apply(base,Brush(1,height_delta_m=math.nan,height_alpha=1))
        self.assertEqual(base,example()[0])

    def test_declared_empty_slot_is_different_from_missing_dependency(self):
        self.assertEqual(resolve_layers(('own-base',None,None),{'own-base':'paint'}),
                         [('Base','paint'),('Coat',None),('Detail',None)])
        with self.assertRaisesRegex(ValueError,'UnknownPaintLayer:Coat'):
            resolve_layers(('own-base','missing',None),{'own-base':'paint'})

    def test_wrong_theme_slot_count_is_diagnostic(self):
        with self.assertRaisesRegex(ValueError,'OwnThemeRequiresThreeSlots'):
            resolve_layers(('base','detail'),{})


if __name__=='__main__':
    unittest.main(verbosity=2)
