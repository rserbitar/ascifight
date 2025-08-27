package main

import (
	"net/http"
	"log"
	"encoding/json"
	"time"
	"fmt"
	"sort"
)

const (
	ServerUrl = "http://127.0.0.1:8000/"
	Team = "Team 1"
	Password = "1"
)

type GameState struct {
	Teams               []string `json:"teams"`
	Actors              []Actor  `json:"actors"`
	Flags               []Flag   `json:"flags"`
	Bases               []Base   `json:"bases"`
	Walls               []Wall   `json:"walls"`
	Scores              Scores   `json:"scores"`
	Tick                int      `json:"tick"`
	TimeOfNextExecution string   `json:"time_of_next_execution"`
}


type OwnedObject interface {
	GetTeam() string
	GetCoordinates() Coordinates
}

type OwnedObjectImpl struct {
	Team        string     `json:"team"`
	Coordinates Coordinates `json:"coordinates"`
}


type Actor struct {
	Type        string     `json:"type"`
	Ident       int        `json:"ident"`
	Flag        string     `json:"flag"`
	OwnedObjectImpl
	
}

func (o OwnedObjectImpl) GetTeam() string {
	return o.Team
}

func (o OwnedObjectImpl) GetCoordinates() Coordinates {
	return o.Coordinates
}

type Flag struct {
	OwnedObjectImpl
}

type Base struct {
	OwnedObjectImpl
}

func filter_objects[t OwnedObject](objs []t, my_team bool) []t {
	filtered := make([]t, 0)
	for _, obj := range(objs) {
		matches := (obj.GetTeam() == Team && my_team) || (obj.GetTeam() != Team && !my_team)
		if matches {
			filtered = append(filtered, obj)
		}
	}
	return filtered
}

type Wall struct {
	X int `json:"x"`
	Y int `json:"y"`
}

type Scores map[string]int

type Coordinates struct {
	X int `json:"x"`
	Y int `json:"y"`
}

type Order struct {
	order_type string
	actor int
	direction string
}

func (o Order) ToUrl() string {
	format := ServerUrl + "orders/%s/%d?direction=%s"
	url := fmt.Sprintf(format, o.order_type, o.actor, o.direction)
	return url
}

type Timing struct {
    Tick                 int     `json:"tick"`
    TimeToNextExecution  float64 `json:"time_to_next_execution"`
    TimeOfNextExecution  string  `json:"time_of_next_execution"`
}

func abs_diff(x int, y int) int {
	if x > y {
		return x - y
	} else {
		return y - x
	}
}

func distance(position Coordinates, target Coordinates) int {
	return abs_diff(target.X, position.X) + abs_diff(target.Y, position.Y)
}

func find_path(position Coordinates, target Coordinates) string {
	if abs_diff(target.X, position.X) > abs_diff(target.Y, position.Y) {
		if position.X > target.X {
			return "left"
		} else {
			return "right"
		}
	} else {
		if position.Y > target.Y {
			return "down"
		} else {
			return "up"
		}
	}
}

func predicted_position(position Coordinates, dir string) Coordinates {
	switch(dir) {
	case "left":
		position.X -= 1
	case "right":
		position.X += 1
	case "down":
		position.Y -= 1
	case "up":
		position.Y += 1
	}
	return position
}

func seek_target[t OwnedObject](actor Actor, target t, action string, orders []Order) []Order {
	direction := find_path(actor.Coordinates, target.GetCoordinates())
	dist := distance(actor.Coordinates, target.GetCoordinates())
	order_type := "move"
	if dist == 1 {
		order_type = action
	}
	orders = append(orders, Order{order_type, actor.Ident, direction})
	if dist == 2 {
		new_position := predicted_position(actor.Coordinates, direction)
		new_direction := find_path(new_position, target.GetCoordinates())
		orders = append(orders, Order{action, actor.Ident, new_direction})
	}
	return orders
}


func generate_orders(state GameState) []Order {
	orders := make([]Order, 0)
	my_actors := filter_objects(state.Actors, true)
	enemy_flags := filter_objects(state.Flags, false)
	my_base := filter_objects(state.Bases, true)[0]
	for _, actor := range(my_actors) {
		if actor.Flag == "" {
			sort.Slice(enemy_flags, func (i, j int) bool {return distance(actor.Coordinates, enemy_flags[i].Coordinates) < distance(actor.Coordinates, enemy_flags[j].Coordinates)})
			nearest_flag := enemy_flags[0]
			orders = seek_target(actor, nearest_flag, "grabput", orders)
		} else {
			orders = seek_target(actor, my_base, "grabput", orders)
		}
	}
	return orders
}

func submit_orders(orders []Order) {
	for _, order := range orders {
		url := order.ToUrl()
		log.Printf("submitting order: %v", order)
		req, err := http.NewRequest("POST", url, nil)
		req.SetBasicAuth(Team, Password)
		client := &http.Client{}
		//resp, err := http.Post(url, "application/json", nil)
		resp, err := client.Do(req)
		if err != nil {
			log.Fatalln(err)
		}
		log.Printf("%d", resp.StatusCode)
		resp.Body.Close()
	}
}

func get_state(t string, v any) {
	url := ServerUrl + "states/" + t
	resp, err := http.Get(url)
	if err != nil {
		log.Fatalln(err)
	}
	defer resp.Body.Close()
	decoder := json.NewDecoder(resp.Body)
	err = decoder.Decode(&v)
	if err != nil {
		log.Fatalln(err)
	}
}

func game_state() (GameState) {
	var state GameState
	get_state("game_state", &state)
	return state
}

func timing() (Timing) {
	var t Timing
	get_state("timing", &t)
	return t
}

func main() {
	current_tick := 0
	for {
		t := timing()
		if t.Tick == current_tick {
			sleep_duration := time.Duration(t.TimeToNextExecution * float64(time.Second))
			time.Sleep(sleep_duration)
		} else {
			current_tick = t.Tick
			state := game_state()
			orders := generate_orders(state)
			submit_orders(orders)
			log.Printf("state received: %v", state)
		}

	}
}
