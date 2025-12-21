"""Defines our purified Spaz modified class (Streamlined)."""

from __future__ import annotations
from typing import override

from nst.utils import clone_object, replace_methods
import bascenev1lib.actor.spaz as vanilla_spaz
from nst.actor.spazfactory import SpazFactory
import bascenev1 as bs

GLOVES_PUNCH_CD = 1000
GLOVES_PUNCH_POWER = 1.7

PICKUP_CD_PERSON_UNIVERSAL = 0.8
PICKUP_CD_OBJECTS = 0

SHIELD_HP = 1000

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
        if (
            not self.node
            or self._dead
            or self.frozen
            or self.node.knockout > 0.0
        ):
            return
        t_ms = int(bs.time() * 1000.0)
        assert isinstance(t_ms, int)
        if t_ms - self.last_bomb_time_ms >= self._bomb_cooldown:
            self.last_bomb_time_ms = t_ms
            self.node.bomb_pressed = True
            if not self.node.hold_node:
                self.drop_bomb()
                sf = SpazFactory.get()
                sf.bomb_sound.play(0.6, position=self.node.position)

        self._turbo_filter_add_press('bomb')

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

    @override
    def equip_shields(self, decay: bool = False, decay_rate: float = 10) -> None:
        """
        Give this spaz a nice energy shield.
        """

        if not self.node:
            logging.exception('Can\'t equip shields; no node.')
            return

        factory = SpazFactory.get()
        if self.shield is None:
            neon_power = 1.25
            shield_color = (max(0.8, self.node.color[0] * 2),
                            max(0.8,self.node.color[1] * 2),
                            max(0.8,self.node.color[2] * 2))

            # Tone down neon colors
            if (self.node.color[0] + self.node.color[1] + self.node.color[2]) > 3.0:
                neon_power = max(self.node.color[0], self.node.color[1], self.node.color[2])


            self.shield = bs.newnode(
                'shield',
                owner=self.node,
                attrs={'color': (shield_color[0] / neon_power,
                                 shield_color[1] / neon_power,
                                 shield_color[2] / neon_power),
                       'radius': 0.95},
            )

            self.node.connectattr('position_center', self.shield, 'position')

        self.shield_hitpoints = SHIELD_HP
        self.shield_decay_rate = decay_rate if decay else 0
        self.shield.hurt = 0
        factory.shield_up_sound.play(1.0, position=self.node.position)

        if self.shield_decay_rate > 0:
            self.shield_decay_timer = bs.Timer(
                0.5, bs.WeakCallPartial(self.shield_decay, decay_rate), repeat=True
            )
            # So user can see the decay.
            self.shield.always_show_health_bar = True

    def set_grab_spaz(self, c: bool):
        if not self.node or not self.node.exists() or not self.is_alive():
            return

        self.can_grab_spaz = c

# Overwrite the vanilla game's spaz init with our own
replace_methods(vanilla_spaz.Spaz, Spaz)