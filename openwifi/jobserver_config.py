import os
import os.path

sqlurl = "sqlite:////"+os.path.abspath(os.path.join(os.path.dirname(__file__),os.pardir))+os.sep+"openwifi.sqlite"
brokerurl = "amqp://guest@localhost//"
redishost = 'localhost'
redisport =  6379
redisdb   = 0
