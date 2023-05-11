import time

import httpx
import vpython

import ascifight.client
import ascifight.util


class CachedGameInfo:
    def __init__(self):
        self.api_cache = {}

    def reset(self):
        self.api_cache = {}

    def information(self, information):
        return self.api_cache.get(information, ascifight.client.get_information(information))


class AsciFight3D:
    def __init__(self):
        self.vobjects = {}
        self.game_information = CachedGameInfo()
        vpython.scene.width = 800
        vpython.scene.height = 800

    def team_to_color(self, team):
        index = self.state['teams'].index(team)
        color_name = ascifight.util.color_names[index]
        return getattr(vpython.color, color_name)

    @property
    def timing(self):
        return self.game_information.information('timing')

    @property
    def rules(self):
        return self.game_information.information('game_rules')

    @property
    def state(self):
        return self.game_information.information('game_state')

    def reset(self):
        for ref, vobject in list(self.vobjects):
            vobject.visible = False
            del self.vobjects[ref]
        assert len(self.vobjects) == 0
        self.initialize_board()

    def set_caption(self):
        vpython.scene.caption = f"""Current score: {self.state['scores']}. 
Current tick: {self.timing['tick']} 

To rotate "camera", drag with right button or Ctrl-drag.
To zoom, drag with middle button or Alt/Option depressed, or use scroll wheel.
On a two-button mouse, middle is left + right.
To pan left/right and up/down, Shift-drag.
Touch screen: pinch/extend to zoom, swipe or two-finger rotate."""

    def initialize_board(self):
        self.game_information.reset()
        self.set_caption()
        map_size = self.rules['map_size']
        vpython.scene.center = vpython.vector(map_size / 2, map_size / 2, 0)
        for x in range(map_size):
            for y in range(map_size):
                new_square = vpython.box(pos=vpython.vector(x, y, 0), length=1, width=0.1, height=1)
                new_square.color = (vpython.color.white, vpython.color.black)[(x + y) % 2]
                self.vobjects[f'square_{x}_{y}'] = new_square

    def update_vobject(self, object_id, **kwargs):
        if object_id in self.vobjects:
            for arg, value in kwargs.items():
                setattr(self.vobjects[object_id], arg, value)
            return True
        return False

    def draw_bases(self):
        for i, base in enumerate(self.state['bases']):
            color = self.team_to_color(base['team'])
            pos = vpython.vector(base['coordinates']['x'], base['coordinates']['y'], 0)
            v_id = f'base_{i}'
            if not self.update_vobject(v_id, pos=pos, color=color):
                self.vobjects[v_id] = vpython.cylinder(pos=pos, axis=vpython.vector(0, 0, 0.5), radius=0.45,
                                                       color=color)

    def update(self):
        self.game_information.reset()
        self.set_caption()

        self.draw_bases()


def game_loop():
    view3d = AsciFight3D()
    current_tick = 2 ** 100
    while True:
        try:
            timing = ascifight.client.get_information("timing")
            if timing["tick"] != current_tick:
                if timing["tick"] < current_tick:
                    view3d.reset()
                view3d.update()
                current_tick = timing["tick"]

            sleep_duration_time = timing["time_to_next_execution"]
            if sleep_duration_time >= 0:
                time.sleep(sleep_duration_time)
        except httpx.ConnectError:
            current_tick = 2 ** 100
            time.sleep(10)
            continue


if __name__ == "__main__":
    game_loop()
