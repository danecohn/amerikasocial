import {API} from '../src/api';
test('wrong reauthentication password preserves the current session while an expired API session signs out',async()=>{
 const client=new API();client.token='synthetic-session';client.onExpired=jest.fn();
 const original=global.fetch;
 global.fetch=jest.fn().mockResolvedValue({ok:false,status:401,json:async()=>({error:'Incorrect password.'})});
 try{await expect(client.request('account/delete',{password:'wrong',confirmation:'DELETE'})).rejects.toThrow('Incorrect password');expect(client.onExpired).not.toHaveBeenCalled();expect(client.token).toBe('synthetic-session');await expect(client.request('feed')).rejects.toThrow();expect(client.onExpired).toHaveBeenCalledTimes(1);}finally{global.fetch=original;}
});
