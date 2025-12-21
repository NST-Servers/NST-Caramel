"""Defines our purified Spaz modified class (Streamlined)."""

from __future__ import annotations
from typing import override

from nst.utils import clone_object, replace_methods
import bascenev1lib.actor.spaz as vanilla_spaz
import bascenev1 as bs

GLOVES_PUNCH_CD = 1000
GLOVES_PUNCH_POWER = 1.7

PICKUP_CD_PERSON_UNIVERSAL = 0.8
PICKUP_CD_OBJECTS = 0

# Clone our vanilla spaz class
# We'll be calling this over "super()" to prevent the code
# from falling apart because the engine is like that. :p
SpazClass: vanilla_spaz.Spaz = clone_object(vanilla_spaz.Spaz)


class Spaz(vanilla_spaz.Spaz):
    """Wrapper for our actor Spaz class."""

    @override
    def __init__(self, *args, **kwargs):
        # Use the cloned SpazClass instead of vanilla_spaz.Spaz
        SpazClass.__init__(self, *args, **kwargs)

        print("Initialized NST Spaz")

        # Our cool attributes
        self.can_grab_spaz = True

    @override
    def on_punch_press(self) -> None:
        SpazClass.on_punch_press(self)

        # Check if we're currently holding a spaz node
        if self.node.hold_node and self.node.hold_node.getnodetype() == 'spaz':
            # Set the longer cooldown when pressing pickup while holding a spaz
            self.set_grab_spaz(False)
            bs.timer(PICKUP_CD_PERSON_UNIVERSAL, bs.CallPartial(self.set_grab_spaz, True))

    @override
    def on_bomb_press(self) -> None:
        SpazClass.on_bomb_press(self)

        # Check if we're currently holding a spaz node
        if self.node.hold_node and self.node.hold_node.getnodetype() == 'spaz':
            # Set the longer cooldown when pressing pickup while holding a spaz
            self.set_grab_spaz(False)
            bs.timer(PICKUP_CD_PERSON_UNIVERSAL, bs.CallPartial(self.set_grab_spaz, True))

    @override
    def on_pickup_press(self) -> None:
        SpazClass.on_pickup_press(self)

        # Check if we're currently holding a spaz node
        if self.node.hold_node and self.node.hold_node.getnodetype() == 'spaz':
            # Set the longer cooldown when pressing pickup while holding a spaz
            self.set_grab_spaz(False)
            bs.timer(PICKUP_CD_PERSON_UNIVERSAL, bs.CallPartial(self.set_grab_spaz, True))


    @override
    def equip_boxing_gloves(self) -> None:
        """
        Give this spaz some boxing gloves.
        """
        assert self.node
        self.node.boxing_gloves = True
        self._has_boxing_gloves = True

        self._punch_power_scale = GLOVES_PUNCH_POWER
        self._punch_cooldown = GLOVES_PUNCH_CD

    def set_grab_spaz(self, c: bool):
        if not self.node or not self.node.exists() or not self.is_alive():
            return

        self.can_grab_spaz = c

# Overwrite the vanilla game's spaz init with our own
replace_methods(vanilla_spaz.Spaz, Spaz)