from locust import HttpUser, task, events, constant_throughput, TaskSet
import random
import gevent
from locust.runners import LocalRunner
from greenlet import greenlet
import time
import os
import numpy as np
from locust import FastHttpUser

# --------------------
#       Locust
# --------------------
MAX_USERS = 962
class DeathStarSocialTasks(TaskSet):
    @task(int(os.environ['LOCUST_HOME_TIMELINE']))
    def read_home_timeline(self):
        user_id = random.randint(0, MAX_USERS - 1)
        start = random.randint(0,100)
        stop = start + 10
        headers = {}
        headers['Content-Type'] = "application/x-www-form-urlencoded"
        response = self.client.get("/wrk2-api/home-timeline/read",params={
            "user_id" : str(user_id),
            "start": str(start),
            "stop": str(stop) 
        }, headers=headers, name="/home-timeline")
    
    @task(int(os.environ['LOCUST_USER_TIMELINE']))
    def read_user_timeline(self):
        user_id = random.randint(0, MAX_USERS - 1)
        start = random.randint(0,100)
        stop = start + 10

        headers = {}
        headers['Content-Type'] = "application/x-www-form-urlencoded"
        response = self.client.get("/wrk2-api/user-timeline/read",params={
            "user_id" : str(user_id),
            "start": str(start),
            "stop": str(stop) 
        }, headers=headers, name="/user-timeline")

    @task(int(os.environ['LOCUST_COMPOSE']))
    def compose_post(self):
        charset = ['q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p', 'a', 's',
            'd', 'f', 'g', 'h', 'j', 'k', 'l', 'z', 'x', 'c', 'v', 'b', 'n', 'm', 'Q',
            'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P', 'A', 'S', 'D', 'F', 'G', 'H',
            'J', 'K', 'L', 'Z', 'X', 'C', 'V', 'B', 'N', 'M', '1', '2', '3', '4', '5',
            '6', '7', '8', '9', '0']
        decset = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0']
        def string_random(length):
            if length > 0:
                return string_random(length - 1) + random.choice(charset)
            else:
                return ""
            
        def dec_random(length):
            if length > 0:
                return dec_random(length - 1) + random.choice(decset)
            else:
                return ""
            
        user_index = random.randint(0,MAX_USERS - 1)
        username = "username_" + str(user_index)
        user_id = str(user_index)
        text = string_random(256)
        num_user_mentions = random.randint(0,5)
        num_urls = random.randint(0,5)
        num_media = random.randint(0,4)
        media_ids = '['
        media_types = '['

        for i in range(num_user_mentions):
            user_mention_id = None
            while True:
                user_mention_id = random.randint(0, MAX_USERS - 1)
                if user_index != user_mention_id:
                    break
            text += " @username_{}".format(user_mention_id)


        for i in range(num_urls):
            text += " http://{}".format(string_random(64))


        for i in range(num_media):
            media_id = dec_random(18)
            media_ids += '\"' + media_id + '\",'
            media_types += '\"png\",'

        media_ids = media_ids[:-1] + "]"
        media_types = media_types[:-1] + "]"

        headers = {}
        headers['Content-Type'] = "application/x-www-form-urlencoded"

        if num_media:
            body = f"username={username}&user_id={user_id}&text={text}&media_ids={media_ids}&media_types={media_types}&post_type=0"
        else:
            body = f"username={username}&user_id={user_id}&text={text}&media_ids=&post_type=0"
        response = self.client.post("/wrk2-api/post/compose", data=body, headers=headers, name="/compose")


class SocialMediaUser(FastHttpUser):
    tasks = [DeathStarSocialTasks]
    wait_time = constant_throughput(10)


