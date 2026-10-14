import * as Notifications from 'expo-notifications';
import Constants from 'expo-constants';
import {api,Actor,Notice} from './api';
export const nativePushAvailable=Constants.executionEnvironment!=='storeClient';
if(nativePushAvailable)Notifications.setNotificationHandler({handleNotification:async()=>({shouldShowBanner:true,shouldShowList:true,shouldPlaySound:false,shouldSetBadge:false})});
export async function notificationActivity(me:Actor,data:Record<string,unknown>){if(!Number.isSafeInteger(data.notificationId)||typeof data.recipient!=='string')return null;if(data.recipient===me.id){const result=await api.request<{notifications:Notice[]}>('notifications');return {notice:result.notifications.find(n=>n.id===data.notificationId),bot:false};}const owned=await api.request<{agents:Actor[]}>('agents');if(!owned.agents.some(a=>a.id===data.recipient))return null;return {bot:true};}
