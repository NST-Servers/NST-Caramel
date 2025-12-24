"""Defines our purified Spaz modified class (Streamlined)."""

from __future__ import annotations
from typing import override

from nst.gameplay import quickturn
from nst.utils import clone_object, replace_methods
import bascenev1lib.actor.spaz as vanilla_spaz
from nst.actor.spazfactory import SpazFactory
import bascenev1 as bs
from bascenev1lib.actor.bomb import Bomb
from bascenev1lib.actor.spaz import BombDiedMessage

GLOVES_PUNCH_CD = 1000
GLOVES_PUNCH_POWER = 1.7

PICKUP_CD_PERSON_UNIVERSAL = 0.8
PICKUP_CD_OBJECTS = 0

SHIELD_HP = 650

HOLD_TO_WAVE_TIME = 0.8

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
        
        # Wave
        self.waving = False
        self.holding_pickup = False
        self.holding_punch = False
        self.wave_sound_node: bs.Node | None = None
        self.hold_to_wave_timer: bs.Timer | None = None
        self.wave_check_timer: bs.Timer | None = None

    @override
    def on_punch_press(self) -> None:
        self.holding_punch = True
        SpazClass.on_punch_press(self)

        # Check if we're currently holding a spaz node
        if hasattr(self.node, 'hold_node') and self.node.hold_node and self.node.hold_node.getnodetype() == 'spaz':
            # Set the longer cooldown when pressing pickup while holding a spaz
            self.set_grab_spaz(False)
            bs.timer(PICKUP_CD_PERSON_UNIVERSAL, bs.CallPartial(self.set_grab_spaz, True))

    @override
    def on_punch_release(self) -> None:
        SpazClass.on_punch_release(self)
        self.holding_punch = False

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
            if not hasattr(self.node, 'hold_node') or not self.node.hold_node:
                self.drop_bomb()

        self._turbo_filter_add_press('bomb')

        # Check if we're currently holding a spaz node.
        if hasattr(self.node, 'hold_node') and self.node.hold_node and self.node.hold_node.getnodetype() == 'spaz':
            # Set the longer cooldown when pressing pickup while holding a spaz
            self.set_grab_spaz(False)
            bs.timer(PICKUP_CD_PERSON_UNIVERSAL, bs.CallPartial(self.set_grab_spaz, True))

    @override
    def on_pickup_press(self) -> None:
        self.holding_pickup = True
        SpazClass.on_pickup_press(self)

        # Check if we're currently holding a spaz node.
        if hasattr(self.node, 'hold_node') and self.node.hold_node and self.node.hold_node.getnodetype() == 'spaz':
            # Set the longer cooldown when pressing pickup while holding a spaz
            self.set_grab_spaz(False)
            bs.timer(PICKUP_CD_PERSON_UNIVERSAL, bs.CallPartial(self.set_grab_spaz, True))

        # Start the hold-to-wave timer only if it doesn't exist yet
        if not self.hold_to_wave_timer:
            if not hasattr(self.node, 'hold_node') or not self.node.hold_node:
                self.hold_to_wave_timer = bs.Timer(HOLD_TO_WAVE_TIME, bs.CallStrict(self.start_waving))

    @override
    def on_pickup_release(self) -> None:
        SpazClass.on_pickup_release(self)
        self.holding_pickup = False

        if self.waving and self.hold_to_wave_timer:
            self.stop_waving()
        elif self.hold_to_wave_timer:
            self.hold_to_wave_timer = None

    def start_waving(self) -> None:
        """Start the continuous waving if pickup is still pressed."""
        if not self.node or not self.node.exists() or not self.is_alive():
            return

        # Only start waving if pickup is still pressed after the hold time
        if self.holding_pickup:
            self.waving = True
            # Create a timer that checks every 0.1s if we should continue waving
            self.wave_check_timer = bs.Timer(0.1, bs.CallStrict(self.check_continue_waving), repeat=True)

    def check_continue_waving(self) -> None:
        """Check if we should continue waving based on pickup button state."""
        if not self.node or not self.node.exists() or not self.is_alive():
            return

        # If pickup is no longer pressed, stop waving
        if not self.holding_pickup or (hasattr(self.node, 'hold_node') and self.node.hold_node):
            self.stop_waving()
        else:
            self.wave()

    def wave(self) -> None:
        """Tell our Spaz to wave."""
        if self.node.exists() and self.is_alive():
            # Only wave for 0.1 seconds at a time
            cel_type = 'celebrate_r' if not self.holding_punch else 'celebrate'
            self.node.handlemessage(cel_type, (HOLD_TO_WAVE_TIME * 1000) / 2.5)

            # Create wave sound if it doesn't exist
            if not self.wave_sound_node:
                self.wave_sound_node = bs.newnode(
                    'sound',
                    owner=self.node,
                    attrs={'sound': SpazFactory.get().waving_sound, 'volume': 0.25},
                )
                self.node.connectattr('position', self.wave_sound_node, 'position')

    def stop_waving(self) -> None:
        """Tell our Spaz to stop waving."""
        if not self.node.exists():
            return

        self.waving = False
        if self.hold_to_wave_timer:
            self.hold_to_wave_timer = None
        if self.wave_sound_node:
            self.wave_sound_node.delete()
            self.wave_sound_node = None
        if self.wave_check_timer:
            self.wave_check_timer = None

    @override
    def drop_bomb(self) -> Bomb | None:
        """
        Tell the spaz to drop one of his bombs, and returns
        the resulting bomb object.
        If the spaz has no bombs or is otherwise unable to
        drop a bomb, returns None.
        """

        if (self.land_mine_count <= 0 and self.bomb_count <= 0) or self.frozen:
            return None
        assert self.node
        pos = self.node.position_forward
        vel = self.node.velocity

        if self.land_mine_count > 0:
            dropping_bomb = False
            self.set_land_mine_count(self.land_mine_count - 1)
            bomb_type = 'land_mine'
        else:
            dropping_bomb = True
            bomb_type = self.bomb_type

        bomb = Bomb(
            position=(pos[0], pos[1] - 0.0, pos[2]),
            velocity=(vel[0], vel[1], vel[2]),
            bomb_type=bomb_type,
            blast_radius=self.blast_radius,
            source_player=self.source_player,
            owner=self.node,
        ).autoretain()
        sf = SpazFactory.get()
        sf.bomb_sound.play(0.6, position=self.node.position)

        assert bomb.node
        if dropping_bomb:
            self.bomb_count -= 1
            bomb.node.add_death_action(
                bs.WeakCallStrict(self.handlemessage, BombDiedMessage())
            )
        self._pick_up(bomb.node)

        for clb in self._dropped_bomb_callbacks:
            clb(self, bomb)

        return bomb

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
                0.5, bs.WeakCallStrict(self.shield_decay), repeat=True
            )
            # So user can see the decay.
            self.shield.always_show_health_bar = True

    def set_grab_spaz(self, c: bool):
        if not self.node or not self.node.exists() or not self.is_alive():
            return

        self.can_grab_spaz = c

# Overwrite the vanilla game's spaz init with our own
replace_methods(vanilla_spaz.Spaz, Spaz)