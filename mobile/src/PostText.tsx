import React from 'react';
import {Alert,Linking,Text} from 'react-native';
import {Actor,api} from './api';
import {problem,Route} from './components';
import {colors,styles as s} from './theme';
export default function PostText({text,open}:{text:string;open:(route:Route)=>void}){const nodes:React.ReactNode[]=[];let last=0;for(const m of text.matchAll(/https?:\/\/[^\s]+|(?<![\w@])@([a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?)|(?<![\p{L}\p{N}_#])#([\p{L}\p{N}_]{1,64})/gu)){nodes.push(text.slice(last,m.index));const follow=async()=>{try{if(m[1])open({kind:'profile',actor:(await api.request<{actor:Actor}>('profile?handle='+encodeURIComponent(m[1]))).actor});else if(m[2])open({kind:'tag',tag:m[2].toLowerCase()});else {const url=new URL(m[0]);if(['https:','http:'].includes(url.protocol))await Linking.openURL(url.href);}}catch(e){Alert.alert('Could not open link',problem(e));}};nodes.push(<Text key={m.index} style={{color:colors.red}} onPress={e=>{e.stopPropagation();void follow();}}>{m[0]}</Text>);last=m.index!+m[0].length;}nodes.push(text.slice(last));return <Text style={s.text}>{nodes}</Text>;}
