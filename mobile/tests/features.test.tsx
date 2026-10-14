import React from 'react';
import {render,screen,fireEvent,waitFor} from '@testing-library/react-native';
import {Actor,api} from '../src/api';
import Communities from '../src/Communities';
import Dating from '../src/Dating';
import Composer from '../src/Composer';
const me:Actor={id:'human',handle:'tester.pds.amerika.social',name:'Tester',kind:'human',bio:''};
afterEach(()=>jest.restoreAllMocks());
test('community detail sends its destination to the native composer',async()=>{
 const group={id:'community',name:'Music Friends',slug:'music-friends',description:'Music and friendship',members:3,posts:0,joined:true,role:'member',archived:false};
 const request=jest.spyOn(api,'request').mockImplementation(async path=>path.startsWith('communities/list')?{communities:[group],cursor:null}:path.startsWith('communities/detail')?{community:group}:{posts:[],cursor:null});
 const compose=jest.fn();await render(<Communities me={me} open={jest.fn()} compose={compose}/>);await screen.findByText('Music Friends');await fireEvent.press(screen.getByText('Open community'));await screen.findByText('Post to community');await fireEvent.press(screen.getByText('Post to community'));expect(compose).toHaveBeenCalledWith({community:'community'});expect(request).toHaveBeenCalledWith('communities/detail?id=community');
});
test('Dating saves an adult-confirmed private draft before permitting photo upload',async()=>{
 const request=jest.spyOn(api,'request').mockImplementation(async(path,body)=>body?{ok:true}:{profile:null,blocked:[],options:{intent:['Both','Dating','Friendship'],gender:['Prefer not to say'],sexuality:['Prefer not to say'],role:['Prefer not to say']}});
 await render(<Dating me={me}/>);await screen.findByText('Save private draft');expect(screen.getByText('Save draft below to add photos')).toBeOnTheScreen();await fireEvent.changeText(screen.getByLabelText('Age (18+)'),'25');await fireEvent(screen.getByLabelText('I am 18 or older and respect consent'),'valueChange',true);await fireEvent.press(screen.getByText('Save private draft'));await waitFor(()=>expect(request).toHaveBeenCalledWith('dating/profile',expect.objectContaining({age:25,adultConfirmed:true,enabled:false,photos:[]})));
});
test('ordinary post composer discovers joined community destinations without changing media ownership',async()=>{
 const request=jest.spyOn(api,'request').mockResolvedValue({communities:[{id:'community',name:'Music Friends',archived:false}],cursor:null});await render(<Composer me={me} draft={{}} onClose={jest.fn()} onSent={jest.fn()}/>);await screen.findByText('Post destination');expect(request).toHaveBeenCalledWith('communities/list?joined=1');
});
