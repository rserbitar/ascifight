import collections
import time

import httpx
import vpython  # type: ignore

import ascifight.client_lib.infra
import ascifight.util


class CachedGameInfo:
    def __init__(self):
        self.api_cache = {}

    def reset(self):
        self.api_cache = {}

    def information(self, information):
        return self.api_cache.get(
            information, ascifight.client_lib.infra.get_game_state()
        )


class AsciFight3D:
    animation_steps = 10

    def __init__(self):
        self.static_vobjects = {}
        self.dynamic_vobjects = {}
        self.game_information = CachedGameInfo()
        self.actor_drawer = collections.defaultdict(lambda: self.new_actor)
        self.animations = {}

        vpython.scene.width = 800
        vpython.scene.height = 800
        vpython.scene.resizable = True
        vpython.distant_light(direction=vpython.vector(0, 1, 0))
        vpython.distant_light(direction=vpython.vector(0, -1, 0))

    def team_index(self, team):
        index = self.state["teams"].index(team)
        return index

    def team_to_color(self, team):
        if team is None:
            return None
        index = self.team_index(team)
        color_name = ascifight.util.color_names[index]
        return getattr(vpython.color, color_name)

    @property
    def timing(self):
        return self.game_information.information("timing")

    @property
    def rules(self):
        return self.game_information.information("game_rules")

    @property
    def state(self):
        return self.game_information.information("game_state")

    def new_step(self):
        self.game_information.reset()
        self.set_caption()
        self.animations = {}
        for vobject in self.dynamic_vobjects.values():
            vobject.ascifight_update = False

    def cleanup(self):
        for ref, vobject in list(self.dynamic_vobjects.items()):
            if hasattr(vobject, "ascifight_update") and not vobject.ascifight_update:
                vobject.visible = False
                del self.static_vobjects[ref]

    def reset(self):
        for ref, vobject in list(self.static_vobjects.items()):
            vobject.visible = False
            del self.static_vobjects[ref]
        for ref, vobject in list(self.dynamic_vobjects.items()):
            vobject.visible = False
            del self.dynamic_vobjects[ref]
        self.initialize_board()

    def fix_text_alignment_errors(self):
        """
        For an unknown reason, vpython.text flips out if the last created compound had
        an origin other than (0,0,0) and totally botches the texts position. Thus,
        before we create any new texts, we create this invisible
        compound that we then delete immediately. This somehow fixes the issue.
        """
        error_fix_box = vpython.box(size=vpython.vector(0.1, 0.1, 0.1))
        error_fix_compound = vpython.compound(
            [error_fix_box], visible=False, origin=vpython.vector(0, 0, 0)
        )
        del error_fix_compound

    def set_caption(self):
        vpython.scene.caption = f"""Current score: {self.state['scores']}. 
Current tick: {self.timing['tick']} 

Drag sides or bottom right corner to resize view.
To rotate "camera", drag with right button or Ctrl-drag.
To zoom, drag with middle button or Alt/Option depressed, or use scroll wheel.
On a two-button mouse, middle is left + right.
To pan left/right and up/down, Shift-drag.
Touch screen: pinch/extend to zoom, swipe or two-finger rotate."""

    def initialize_board(self):
        self.new_step()
        self.fix_text_alignment_errors()
        map_size = self.rules["map_size"]
        vpython.scene.center = vpython.vector(map_size / 2, map_size / 2, 0)
        for x in range(map_size):
            for y in range(map_size):
                new_square = vpython.box(
                    pos=vpython.vector(x, y, 0),
                    length=1,
                    width=0.1,
                    height=1,
                    color=(vpython.color.white, vpython.color.gray(luminance=0.2))[
                        (x + y) % 2
                    ],
                    texture=vpython.textures.granite,
                )
                self.static_vobjects[f"square_{x}_{y}"] = new_square
            new_text_x = vpython.text(
                pos=vpython.vector(x - 0.4, -1, 0),
                align="left",
                color=vpython.color.white,
                height=0.8,
                depth=0.1,
                text=str(x),
                axis=vpython.vector(0, -1, 0),
            )
            new_text_y = vpython.text(
                pos=vpython.vector(-1, x - 0.4, 0),
                align="right",
                color=vpython.color.white,
                height=0.8,
                depth=0.1,
                text=str(x),
            )
            self.static_vobjects[f"label_x_{x}"] = new_text_x
            self.static_vobjects[f"label_y_{x}"] = new_text_y
        label_x = vpython.text(
            pos=vpython.vector(map_size, -2, 0),
            align="left",
            color=vpython.color.white,
            height=0.8,
            depth=0.1,
            text="X",
        )
        label_y = vpython.text(
            pos=vpython.vector(-1, map_size, 0),
            align="right",
            color=vpython.color.white,
            height=0.8,
            depth=0.1,
            text="Y",
        )
        self.static_vobjects["label_x"] = label_x
        self.static_vobjects["label_y"] = label_y

    def move_vobject(self, object_id, pos):
        if object_id in self.dynamic_vobjects:
            old_pos = self.dynamic_vobjects[object_id].pos
            if old_pos != pos:
                dpos = (pos - old_pos) / self.animation_steps
                self.animations[object_id] = (dpos, pos)
            self.dynamic_vobjects[object_id].ascifight_update = True
            return True
        return False

    def teleport_vobject(self, object_id, pos):
        if object_id in self.dynamic_vobjects:
            self.dynamic_vobjects[object_id].pos = pos
            self.dynamic_vobjects[object_id].ascifight_update = True
            return True
        return False

    @staticmethod
    def coordinates_to_vector(coordinates):
        return vpython.vector(coordinates["x"], coordinates["y"], 0)

    def move_or_create(self, v_id, game_object, drawer):
        pos = self.coordinates_to_vector(game_object["coordinates"])
        if not self.move_vobject(v_id, pos):
            color = self.team_to_color(game_object["team"])
            self.dynamic_vobjects[v_id] = drawer(pos, color, game_object)

    def teleport_or_create(self, v_id, game_object, drawer):
        pos = self.coordinates_to_vector(game_object["coordinates"])
        if not self.teleport_vobject(v_id, pos):
            color = self.team_to_color(game_object["team"])
            self.dynamic_vobjects[v_id] = drawer(pos, color, game_object)

    def new_base(self, pos, color, game_object):
        return vpython.cone(
            pos=pos,
            radius=0.45,
            axis=vpython.vector(0, 0, 1.5),
            color=color,
            texture={
                "file": vpython.textures.wood_old,
                "bumpmap": vpython.bumpmaps.wood_old,
            },
        )

    def new_actor(self, pos, color, game_object):
        self.fix_text_alignment_errors()
        cylinder = vpython.cylinder(
            pos=pos,
            color=color,
            radius=0.45,
            axis=vpython.vector(0, 0, 0.5),
        )
        text = vpython.text(
            text=f"{game_object['type'][0]}{game_object['ident']}",
            pos=pos + vpython.vector(0, -0.2, 0),
            depth=0.55,
            color=vpython.color.black,
            height=0.4,
            align="center",
        )
        runner = vpython.compound(
            [cylinder, text],
            origin=pos,
            texture={
                "file": vpython.textures.metal,
                "bumpmap": vpython.bumpmaps.stucco,
            },
        )
        return runner

    def new_flag(self, pos, color, game_object):
        handle = vpython.cylinder(
            color=vpython.vector(0.72, 0.42, 0),
            axis=vpython.vector(0, 0, 3),
            radius=0.05,
            pos=pos,
        )
        head = vpython.box(
            color=color,
            pos=pos + vpython.vector(0.45, 0, 3),
            length=1,
            width=0.7,
            height=0.1,
        )
        flag = vpython.compound(
            [handle, head], origin=pos, texture=vpython.textures.rug
        )
        return flag

    def new_wall(self, pos, color, game_object):
        box = vpython.box(
            color=vpython.color.gray(luminance=0.4),
            pos=pos + vpython.vector(0, 0, 0.5),
            height=1,
            width=1,
            length=1,
        )
        wall = vpython.compound(
            [box],
            origin=pos,
            texture={"file": vpython.textures.rock, "bumpmap": vpython.bumpmaps.rock},
        )
        return wall

    def draw_bases(self):
        for i, base in enumerate(self.state["bases"]):
            v_id = f"base_{i}"
            self.move_or_create(v_id, base, self.new_base)

    def draw_actors(self):
        for i, actor in enumerate(self.state["actors"]):
            actor_type = actor["type"]
            index1 = self.team_index(actor["team"])
            index2 = actor["ident"]
            v_id = f"{actor_type}_{index1}_{index2}"
            draw_function = self.actor_drawer[actor_type]
            self.move_or_create(v_id, actor, draw_function)

    def draw_flags(self):
        for i, flag in enumerate(self.state["flags"]):
            v_id = f"flag_{i}"
            self.move_or_create(v_id, flag, self.new_flag)

    def draw_walls(self):
        for i, wall in enumerate(self.state["walls"]):
            v_id = f"wall_{i}"
            wall_object = {"coordinates": wall, "team": None}
            self.teleport_or_create(v_id, wall_object, self.new_wall)

    def update(self):
        self.new_step()
        print(self.state)
        self.draw_bases()
        self.draw_actors()
        self.draw_flags()
        self.draw_walls()
        self.animate()
        self.cleanup()

    def animate(self):
        for i in range(self.animation_steps):
            for v_id, (dpos, _) in self.animations.items():
                self.dynamic_vobjects[v_id].pos += dpos
            vpython.rate(60)
        # Avoid floating point inaccuracies
        for v_id, (_, new_pos) in self.animations.items():
            self.dynamic_vobjects[v_id].pos = new_pos


def game_loop():
    view3d = AsciFight3D()
    current_tick = 2**100
    while True:
        try:
            timing = ascifight.client_lib.infra.get_timing()
            if timing.tick != current_tick:
                if timing.tick < current_tick:
                    view3d.reset()
                view3d.update()
                current_tick = timing.tick

            sleep_duration_time = timing.time_to_next_execution
            if sleep_duration_time >= 0:
                time.sleep(sleep_duration_time)
        except httpx.ConnectError:
            current_tick = 2**100
            time.sleep(10)
            continue


if __name__ == "__main__":
    game_loop()
