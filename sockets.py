#!/usr/bin/env python
# coding: utf-8
# Copyright (c) 2013-2014 Abram Hindle
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import flask
from flask import Flask, request
from flask_sockets import Sockets
import gevent
from gevent import queue
import time
import json
app = Flask(__name__)
sockets = Sockets(app)
app.debug = True

class World:
    def __init__(self):
        self.clear()
        # we've got listeners now!
        self.listeners = list()
        
    def add_set_listener(self, listener):
        self.listeners.append( listener )

    def update(self, entity, key, value):
        entry = self.space.get(entity,dict())
        entry[key] = value
        self.space[entity] = entry
        self.update_listeners( entity )

    def set(self, entity, data):
        self.space[entity] = data
        self.update_listeners( entity )

    def update_listeners(self, entity):
        '''update the set listeners'''
        for listener in self.listeners:
            listener(entity, self.get(entity))

    def clear(self):
        self.space = dict()

    def get(self, entity):
        return self.space.get(entity,dict())
    
    def world(self):
        return self.space


class SocketHandler:
    def __init__(self, queue):
        self.sockets = dict()
        self.queue = queue

    def send(self, entity, data):
        packet = json.dumps({entity:data})
        marked_dead = []
        
        self.queue.put(packet)
        for client, socket in self.sockets.items():
            if (socket.closed == False):
                socket.send(packet)
            else:
                marked_dead.append(client)
        
        for dead in marked_dead:
            self.unregister(dead)
    
    def register(self, name, socket):
        self.sockets[name] = socket
    
    def unregister(self, name):
        del self.sockets[name]

            
myWorld = World()        
queue = queue.Queue()
socket_handler = SocketHandler(queue)

myWorld.add_set_listener( socket_handler.send )

 
@app.route('/')
def hello():
    '''Return something coherent here.. perhaps redirect to /static/index.html '''
    return flask.redirect("/static/index.html")

def read_ws(ws, client):
    '''A greenlet function that reads from the websocket and updates the world'''
    while not ws.closed:
        msg = ws.receive()
        if (msg is not None):
            packet = json.loads( msg )
            key, value = list(packet.items())[0]
            myWorld.set(key, value)

        gevent.sleep(0.1)

@sockets.route('/subscribe')
def subscribe_socket(ws):
    '''Fufill the websocket URL of /subscribe, every update notify the
       websocket and read updates from the websocket'''
    
    
    client = str(time.time())
    socket_handler.register(client, ws)
    while not ws.closed:
        msg = ws.receive()
        if (msg is not None):
            packet = json.loads(msg)
            key, value = list(packet.items())[0]
            myWorld.set(key, value)
        gevent.sleep(0.1)


# I give this to you, this is how you get the raw body/data portion of a post in flask
# this should come with flask but whatever, it's not my project.
def flask_post_json():
    '''Ah the joys of frameworks! They do so much work for you
       that they get in the way of sane operation!'''
    if (request.json != None):
        return request.json
    elif (request.data != None and request.data.decode("utf8") != u''):
        return json.loads(request.data.decode("utf8"))
    else:
        return json.loads(request.form.keys()[0])

@app.route("/entity/<entity>", methods=['POST','PUT'])
def update(entity):
    '''update the entities via this interface'''
    myWorld.set(entity, flask_post_json())
    return myWorld.get(entity)

@app.route("/world", methods=['POST','GET'])    
def world():
    '''you should probably return the world here'''
    return myWorld.world()

@app.route("/entity/<entity>")    
def get_entity(entity):
    '''This is the GET version of the entity interface, return a representation of the entity'''
    return myWorld.get(entity)


@app.route("/clear", methods=['POST','GET'])
def clear():
    '''Clear the world out!'''
    myWorld.clear()
    return myWorld.world()




if __name__ == "__main__":
    ''' This doesn't work well anymore:
        pip install gunicorn
        and run
        gunicorn -k flask_sockets.worker sockets:app
    '''
   
    app.run()
