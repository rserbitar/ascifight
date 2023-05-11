import collections
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
        self.static_vobjects = {}
        self.dynamic_vobjects = {}
        self.game_information = CachedGameInfo()
        self.actor_drawer = collections.defaultdict(self.draw_new_runner)
        self.actor_drawer['Runner'] = self.draw_new_runner

        vpython.scene.width = 800
        vpython.scene.height = 800

    def team_index(self, team):
        index = self.state['teams'].index(team)
        return index

    def team_to_color(self, team):
        index = self.team_index(team)
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

    def new_step(self):
        self.game_information.reset()
        self.set_caption()
        for vobject in self.dynamic_vobjects.values():
            vobject.ascifight_update = False

    def cleanup(self):
        for ref, vobject in list(self.dynamic_vobjects.items()):
            if hasattr(vobject, 'ascifight_update') and not vobject.ascifight_update:
                vobject.visible = False
                del self.static_vobjects[ref]

    def reset(self):
        for ref, vobject in list(self.static_vobjects.items()):
            vobject.visible = False
            del self.static_vobjects[ref]
        for ref, vobject in list(self.dynamic_vobjects.items()):
            vobject.visible = False
            del self.static_vobjects[ref]
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
        self.new_step()
        map_size = self.rules['map_size']
        vpython.scene.center = vpython.vector(map_size / 2, map_size / 2, 0)
        for x in range(map_size):
            for y in range(map_size):
                new_square = vpython.box(pos=vpython.vector(x, y, 0), length=1, width=0.1, height=1,
                                         color=(vpython.color.white, vpython.color.black)[(x + y) % 2])
                self.static_vobjects[f'square_{x}_{y}'] = new_square
            new_text_x = vpython.text(pos=vpython.vector(x - 0.4, -1, 0), align='left', color=vpython.color.white,
                                      height=0.8, depth=0.1, text=str(x), axis=vpython.vector(0, -1, 0))
            new_text_y = vpython.text(pos=vpython.vector(-1, x - 0.4, 0), align='right', color=vpython.color.white,
                                      height=0.8, depth=0.1, text=str(x))
            self.static_vobjects[f'label_x_{x}'] = new_text_x
            self.static_vobjects[f'label_y_{x}'] = new_text_y

    def move_vobject(self, object_id, pos):
        if object_id in self.dynamic_vobjects:
            self.dynamic_vobjects[object_id].pos = pos
            self.dynamic_vobjects[object_id].ascifight_update = True
            return True
        return False

    @staticmethod
    def coordinates_to_vector(coordinates):
        return vpython.vector(coordinates['x'], coordinates['y'], 0)

    def draw_bases(self):
        for i, base in enumerate(self.state['bases']):
            pos = self.coordinates_to_vector(base['coordinates'])
            v_id = f'base_{i}'
            if not self.move_vobject(v_id, pos):
                color = self.team_to_color(base['team'])
                self.dynamic_vobjects[v_id] = vpython.cylinder(pos=pos, axis=vpython.vector(0, 0, 0.5), radius=0.45,
                                                               color=color)

    def draw_new_runner(self, pos, color):
        return vpython.cone(pos=pos, color=color, radius=0.3, axis=vpython.vector(0, 0, 1))

    def draw_actors(self):
        for i, actor in enumerate(self.state['actors']):
            actor_type = actor['type']
            index1 = self.team_index(actor['team'])
            index2 = actor['ident']
            v_id = f'{actor_type}_{index1}_{index2}'
            pos = self.coordinates_to_vector(actor['coordinates'])

            if not self.move_vobject(v_id, pos):
                draw_function = self.actor_drawer[actor_type]
                color = self.team_to_color(actor['team'])
                self.dynamic_vobjects[v_id] = draw_function(pos, color)

    def update(self):
        self.new_step()
        self.draw_bases()
        self.draw_actors()
        print(self.state)
        self.cleanup()


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
