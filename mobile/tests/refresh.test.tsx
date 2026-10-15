import React, {useState} from 'react';
import {Text, ScrollView} from 'react-native';
import {render, screen, fireEvent, waitFor, act} from '@testing-library/react-native';
import {api} from '../src/api';
import {Page, Field, useResource} from '../src/ui';
import Paged from '../src/Paged';

afterEach(() => jest.restoreAllMocks());
function Draft() {
  const [draft, setDraft] = useState('');
  const {data} = useResource<{name:string}>('refresh-fixture');
  return <><Field label="Unsaved bio" value={draft} onChange={setDraft}/><Text>{data?.name}</Text></>;
}
test('header refresh reloads resources without clearing unsaved input', async () => {
  const request = jest.spyOn(api, 'request').mockResolvedValueOnce({name:'Before'}).mockResolvedValue({name:'After'});
  await render(<Page title="Settings" onClose={jest.fn()}><Draft/></Page>);
  await screen.findByText('Before');
  await fireEvent.changeText(screen.getByLabelText('Unsaved bio'), 'Keep this draft');
  await fireEvent.press(screen.getByLabelText('Refresh page'));
  await screen.findByText('After');
  expect(request).toHaveBeenCalledTimes(2);
  expect(screen.getByLabelText('Unsaved bio')).toHaveProp('value', 'Keep this draft');
});
test('pull refresh resets a paginated list and waits for its response', async () => {
  jest.spyOn(api, 'request').mockResolvedValueOnce({rows:[{id:'1',name:'Old row'}],cursor:null}).mockResolvedValue({rows:[{id:'2',name:'New row'}],cursor:null});
  await render(<Page title="Community" onClose={jest.fn()}><Paged path="rows" field="rows" render={row=><Text>{row.name}</Text>}/></Page>);
  await screen.findByText('Old row');
  const scroll = screen.getByTestId('feature-page-scroll');
  await act(async () => { scroll.props.refreshControl.props.onRefresh(); });
  await screen.findByText('New row');
  expect(screen.queryByText('Old row')).toBeNull();
  await waitFor(() => expect(screen.getByTestId('feature-page-scroll').props.refreshControl.props.refreshing).toBe(false));
});
