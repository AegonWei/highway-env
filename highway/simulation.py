from __future__ import division, print_function

import numpy as np
import datetime
import pygame
import shutil
import os

from highway.agent.graphics import AgentGraphics
from highway.vehicle.control import MDPVehicle
from highway.road.road import Road
from highway.road.graphics import WindowSurface, RoadGraphics
from highway.mdp.road_mdp import RoadMDP
from highway.agent.ttc_vi import TTCVIAgent
from highway.vehicle.graphics import VehicleGraphics


class Simulation:
    SCREEN_WIDTH = 600
    SCREEN_HEIGHT = 150
    FPS = 15
    POLICY_FREQUENCY = 1
    TRAJECTORY_TIMESTEP = 0.35
    DISPLAY_AGENT = True

    RECORD_VIDEO = True
    VIDEO_SPEED = 2
    MAXIMUM_VIDEO_LENGTH = 5*60*FPS
    OUT_FOLDER = 'out'
    TMP_FOLDER = os.path.join(OUT_FOLDER, 'tmp')

    def __init__(self, road, ego_vehicle_type=None, agent_type=TTCVIAgent, displayed=True):
        self.road = road
        if ego_vehicle_type:
            self.vehicle = ego_vehicle_type.create_random(self.road, 25)
            self.road.vehicles.append(self.vehicle)
        else:
            self.vehicle = None
        self.displayed = displayed

        self.t = 0
        self.frame_count = 0
        self.dt = 1 / self.FPS
        self.done = False
        self.pause = False
        self.trajectory = None
        if agent_type and self.vehicle and isinstance(self.vehicle, MDPVehicle):
            self.agent = agent_type(RoadMDP(self.vehicle))
        else:
            self.agent = None

        if self.displayed:
            pygame.init()
            pygame.display.set_caption("Highway")
            if self.DISPLAY_AGENT:
                self.SCREEN_HEIGHT *= 2
                panel_size = (self.SCREEN_WIDTH, self.SCREEN_HEIGHT/2)
                self.agent_surface = pygame.Surface(panel_size)
            else:
                panel_size = (self.SCREEN_WIDTH, self.SCREEN_HEIGHT)
            self.screen = pygame.display.set_mode([self.SCREEN_WIDTH, self.SCREEN_HEIGHT])
            self.road_surface = WindowSurface(panel_size, 0, pygame.Surface(panel_size))
            self.clock = pygame.time.Clock()

            if self.RECORD_VIDEO:
                self.make_video_dir()
                self.video_name = 'highway_{}'.format(datetime.datetime.now().strftime('%Y-%m-%d-%H:%M:%S'))

    def process(self):
        self.handle_events()
        self.act()
        self.step()
        self.display()

    def handle_events(self):
        if self.displayed:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.done = True
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        self.pause = not self.pause
                self.road_surface.handle_event(event)
                if self.vehicle:
                    VehicleGraphics.handle_event(self.vehicle, event)

    def act(self):
        if self.pause:
            return

        # Default action for all vehicles
        self.road.act()

        # Planning for ego-vehicle
        policy_call = self.t % (self.FPS // self.POLICY_FREQUENCY) == 0
        if self.agent and policy_call:
            mdp = RoadMDP(self.vehicle, action_timestep=1/self.FPS, action_duration=1/self.POLICY_FREQUENCY).simplified()
            actions = self.agent.plan(mdp)
            self.trajectory = self.vehicle.predict_trajectory(actions,
                                                              1/self.POLICY_FREQUENCY,
                                                              self.TRAJECTORY_TIMESTEP,
                                                              self.dt)
            if actions:
                self.vehicle.act(actions[0])

    def step(self):
        if not self.pause:
            self.road.step(self.dt)
            self.t += 1

    def window_position(self):
        return self.vehicle.position if self.vehicle else np.array([0, len(self.road.lanes) / 2 * 4])

    def display(self):
        if not self.displayed:
            return

        self.road_surface.move_display_window_to(self.window_position())
        RoadGraphics.display(self.road, self.road_surface)
        if self.trajectory:
            VehicleGraphics.display_trajectory(self.trajectory, self.road_surface)
        RoadGraphics.display_traffic(self.road, self.road_surface)
        self.screen.blit(self.road_surface, (0, 0))

        if self.DISPLAY_AGENT and self.agent:
            AgentGraphics.display(self.agent, self.agent_surface)
            self.screen.blit(self.agent_surface, (0, self.SCREEN_HEIGHT / 2))
        self.clock.tick(self.FPS)
        pygame.display.flip()

        if self.RECORD_VIDEO and not self.pause:
            pygame.image.save(self.screen, "{}/{}_{:04d}.bmp".format(self.TMP_FOLDER, self.video_name, self.frame_count))
            self.frame_count += 1
            if self.t > self.MAXIMUM_VIDEO_LENGTH \
                    or (self.vehicle.crashed and self.vehicle.velocity < 1) \
                    or ((len(self.road.vehicles) > 1) and (self.vehicle.position[0] > 50
                        + np.max([o.position[0] for o in self.road.vehicles if o is not self.vehicle]))):
                self.done = True

    def make_video_dir(self):
        if not os.path.exists(self.OUT_FOLDER):
            os.mkdir(self.OUT_FOLDER)
        self.clear_video_dir()
        os.mkdir(self.TMP_FOLDER)

    def clear_video_dir(self):
        if os.path.exists(self.TMP_FOLDER):
            shutil.rmtree(self.TMP_FOLDER, ignore_errors=True)

    def quit(self):
        if self.displayed:
            pygame.quit()
            if self.RECORD_VIDEO:
                os.system("ffmpeg -r {3} -i {0}/{2}_%04d.bmp -vcodec libx264 -crf 25 {1}/{2}.avi"
                          .format(self.TMP_FOLDER, self.OUT_FOLDER, self.video_name, self.FPS*self.VIDEO_SPEED))
                delay = int(np.round(100/(self.VIDEO_SPEED*self.FPS)))
                os.system("convert -delay {3} -loop 0 {0}/{2}*.bmp {1}/{2}.gif"
                          .format(self.TMP_FOLDER, self.OUT_FOLDER, self.video_name, delay))
                self.clear_video_dir()


def test():
    from highway.vehicle.behavior import IDMVehicle
    road = Road.create_random_road(lanes_count=4, lane_width=4.0, vehicles_count=5, vehicles_type=IDMVehicle)
    sim = Simulation(road, ego_vehicle_type=MDPVehicle)
    while not sim.done:
        sim.process()
    sim.quit()


if __name__ == '__main__':
    test()
