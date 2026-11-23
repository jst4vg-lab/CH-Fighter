"""Normalized message event store shared with future consumers."""
import threading
from collections import deque

class MessageEventStore:
    def __init__(self):
        self.lock=threading.RLock();self.messages={};self.events=deque(maxlen=1000);self.sequence=0

    def publish(self,kind,channel_id,message_id,data=None):
        channel_id=str(channel_id); message_id=str(message_id)
        with self.lock:
            key=(channel_id,message_id)
            if kind=='delete': self.messages.pop(key,None)
            elif data: self.messages[key]=data
            self.sequence+=1; self.events.append({'sequence':self.sequence,'type':kind,'channel_id':channel_id,'message_id':message_id,'message':data})

