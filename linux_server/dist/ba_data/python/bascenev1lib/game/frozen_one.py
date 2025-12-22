# Ported by your friend: Freaku


import babase
import bascenev1 as bs
from bascenev1lib.game.chosenone import Player, ChosenOneGame
from bascenev1lib.actor.flag import Flag


# ba_meta require api 9
# ba_meta export bascenev1.GameActivity
class FrozenOneGame(ChosenOneGame):
    name = 'Frozen One'

    def _set_chosen_one_player(self, player: Player | None) -> None:
        existing = self._get_chosen_one_player()
        if existing:
            existing.chosen_light = None
        self._swipsound.play()
        if not player:
            assert self._flag_spawn_pos is not None
            self._flag = Flag(
                color=(0.341, 0.922, 1),
                position=self._flag_spawn_pos,
                touchable=False,
            )
            self._chosen_one_player = None

            # Create a light to highlight the flag;
            # this will go away when the flag dies.
            bs.newnode(
                'light',
                owner=self._flag.node,
                attrs={
                    'position': self._flag_spawn_pos,
                    'intensity': 0.6,
                    'height_attenuated': False,
                    'volume_intensity_scale': 0.1,
                    'radius': 0.1,
                    'color': (0.341, 0.922, 1),
                },
            )

            # Also an extra momentary flash.
            self._flash_flag_spawn()

            # Re-create our flag region in case if someone is waiting for
            # flag right there:
            self._create_reset_region()
        else:
            if player.actor:
                self._flag = None
                self._chosen_one_player = player

                if self._chosen_one_gets_shield:
                    player.actor.handlemessage(bs.PowerupMessage('shield'))
                if self._chosen_one_gets_gloves:
                    player.actor.handlemessage(bs.PowerupMessage('punch'))

                # Use a color that's partway between their team color
                # and white.
                light = player.chosen_light = bs.NodeActor(
                    bs.newnode(
                        'light',
                        attrs={
                            'intensity': 0.6,
                            'height_attenuated': False,
                            'volume_intensity_scale': 0.1,
                            'radius': 0.13,
                            'color': (0.341, 0.922, 1),
                        },
                    )
                )

                assert light.node
                bs.animate(
                    light.node,
                    'intensity',
                    {0: 1.0, 0.2: 0.4, 0.4: 1.0},
                    loop=True,
                )
                assert isinstance(player.actor, PlayerSpaz)
                player.actor.node.connectattr(
                    'position', light.node, 'position'
                )

        if hasattr(player, 'actor'):
            player.actor.frozen = True
            player.actor.node.frozen = 1
