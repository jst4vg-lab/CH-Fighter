"""Explicitly unavailable outgoing provider."""
class DisabledWriteProvider:
    def __init__(self,reason='Sending is disabled'):
        self.reason=reason
    def status(self):
        return {'provider':'disabled','state':'unavailable','reason':self.reason,'channel_id':None,
                'sender_id':None,'capabilities':{'send':False,'reply':False,'attach':False}}

    def send(self, draft_id, text, paths, reply_to_id=''):
        return {'ok':False,'code':'provider_unavailable'}


