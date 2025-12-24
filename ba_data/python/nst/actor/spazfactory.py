"""Defines our purified SpazFactory modified class."""

from __future__ import annotations
from typing import override

import bascenev1 as bs
from nst.utils import clone_object, replace_methods
import bascenev1lib.actor.spazfactory as vanilla_spazfactory

# clone original to use functions later on
VanillaSpazFactory: vanilla_spazfactory.SpazFactory = clone_object(
    vanilla_spazfactory.SpazFactory
)


class SpazFactory(vanilla_spazfactory.SpazFactory):
    """
    New SpazFactory that is streamlined.
    It contains all the assets from the vanilla factory
    and adds one new sound.
    """

    @override
    def __init__(self, *args, **kwargs):
        VanillaSpazFactory.__init__(self, *args, **kwargs)

        self.bomb_sound = bs.getsound('pop01')
        self.quickturn_sound = bs.getsound('swish2')
        self.waving_sound = bs.getsound('punchSwish')
        self.woo_sound = bs.getsound('woo3')
        self.orchestra_hit_sound = bs.getsound('orchestraHitBig1')
        self.orchestra_hit2_sound = bs.getsound('orchestraHit3')



# Overwrite the vanilla game's spaz factory with our own
replace_methods(vanilla_spazfactory.SpazFactory, SpazFactory)
