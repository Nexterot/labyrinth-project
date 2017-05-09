# -*- coding: utf-8 -*-

import random

import server_tools
from game import fields
from game.constants import *


class Player:
    """ player for the game """
    MAX_HEALTH = 4

    def __init__(self, game, name):
        self.game = game
        self.name = name
        self.location = None
        self.vector = (0, 0)
        self.health = Player.MAX_HEALTH
        self.visible_fields = [False] * (len(game.level) * len(game.level[0]))
        self.inventory = [0, 0, 0]
        self.has_treasure = False

    def __vector_to(self, obj):
        """ calculates vector distance to object """
        shift_x, shift_y = map((lambda x, y: x - y), obj.coordinates, self.location.coordinates)
        return shift_x, shift_y

    def go(self, field):
        """ player movement logic """
        save_location = self.location

        # создаем пустой пакет для отправки клиенту
        result = server_tools.create_packet()

        # текущие координаты
        result["coordinates"] = self.location.coordinates

        # если клетка не рядом
        if not self.can_go(field):
            result["error"] = 1
            return result, True

        self.visible_fields[field.id] = True

        # если стена
        if isinstance(field, fields.Wall):
            # self.vector = (0, 0)
            result["wall"] = [1, field.coordinates[0], field.coordinates[1]]
            return result, False

        # помещаем коориданты клетки, на которую перейдем
        result["coordinates"] = field.coordinates

        # передвинуть игрока
        self.move(field)

        # если на клетке стоит медведь
        if self.game.bear.location == field:
            self.vector = self.__vector_to(field)
            self.game.bear.attack(self)
            if self.health == 0:
                result["bear"] = 1
            elif self.health == 2:
                result["bear"] = 2
            elif self.health == 1:
                result["bear"] = 3
            return result, False

        # если обычная клетка
        if isinstance(field, fields.Grass):
            # если клетка - выход из лабиринта
            if field.exit:
                result["exit"][0] = 1
                if self.has_treasure:
                    result["exit"][1] = 1  # выиграл
                    self.game.winner = self
                else:
                    result["exit"][1] = 0  # нужно откинуть
                    # передвинуть игрока
                    self.move(save_location)

            # если на этой клетке лежит аптечка
            if field.obj == "hospital":
                if self.health == 0:
                    result["aid"] = 1
                    self.heal()
                elif self.health < Player.MAX_HEALTH:
                    result["aid"] = 2
                    self.heal()
                else:
                    result["aid"] = 3
                    self.inventory[AID] += 1

            # если на этой клетке лежит вооружение
            if field.obj == "ammo":
                if random.randrange(1, 3) == 1:  # +1 цемент
                    self.inventory[CONCRETE] += 1
                    result["arm"] = 1
                else:  # +1 бомба
                    self.inventory[BOMB] += 1
                    result["arm"] = 2

            # если мина
            if field.obj == "mine":
                self.get_damage(2)
                if self.health == 0:
                    result["mine"] = 1
                elif self.health == 2:
                    result["mine"] = 2
                elif self.health == 1:
                    result["mine"] = 3
                field.delete_object()

            # сокровище :)
            if field.has_treasure:
                if self.alive:
                    self.has_treasure = True
                    field.has_treasure = False
                    result["treasure"] = 1
                    # todo уведомить остальных игроков, что клад найден мною
                    print("Игрок {} нашел клад!".format(self.name))

            # если телепорт
            if field.obj in {"tp1", "tp2", "tp3"}:
                result["metro"] = [1, *field.pair.coordinates]
                self.visible_fields[field.pair.id] = True
                self.teleport_from(field)

        # flow down (and left) the river
        if isinstance(field, fields.Water):
            river_info = [1, []]
            vector = self.vector
            washed_away = False

            while not washed_away:
                next_water_down = self.game.fields.at((field.coordinates[0] + 1, field.coordinates[1]))
                next_water_left = self.game.fields.at((field.coordinates[0], field.coordinates[1] - 1))
                if isinstance(next_water_down, fields.Water):
                    self.move(next_water_down)
                    self.visible_fields[next_water_down.id] = True
                    field = next_water_down
                elif isinstance(next_water_left, fields.Water):
                    self.move(next_water_left)
                    self.visible_fields[next_water_left.id] = True
                    field = next_water_left
                else:
                    washed_away = True
                    self.visible_fields[field.id] = True
                river_info[1].append(self.location.coordinates)

            result["river"] = river_info
            self.vector = vector

        return result, False

    def move(self, field):
        """ make a move """
        self.vector = self.__vector_to(field)
        self.location = field

    def teleport_from(self, field):
        self.location = field.pair

    def look(self, field):
        if self.can_look(field):
            self.visible_fields[field.id] = True
            self.vector = (0, 0)

    def can_go(self, field):
        """ returns True if self.location is adjacent to field (excluding diagonals) """
        shift_x, shift_y = map((lambda x, y: x - y), field.coordinates, self.location.coordinates)
        return abs(shift_x) + abs(shift_y) == 1

    def can_look(self, field):
        """ returns True if self.location is adjacent to field (including diagonals) """
        shift_x, shift_y = map((lambda x, y: x - y), field.coordinates, self.location.coordinates)
        return abs(shift_x) | abs(shift_y) == 1

    def heal(self):
        self.health = Player.MAX_HEALTH

    def get_damage(self, damage):
        self.health -= damage
        if self.health <= 0:
            self.health = 0
            if self.has_treasure:
                self.has_treasure = False
                self.location.has_treasure = True
                print("Игрок {} потерял сокровище".format(self.name))

    def get_pushed(self, from_obj):
        pass

    @property
    def alive(self):
        return self.health > 0