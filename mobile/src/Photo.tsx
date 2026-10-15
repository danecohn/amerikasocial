import React,{useEffect,useState} from 'react';
import {Image,Modal,Pressable,ScrollView,Text,useWindowDimensions,View} from 'react-native';
import {SafeAreaView} from 'react-native-safe-area-context';
import {Button} from './components';
import {styles as s} from './theme';
export default function Photo({uri,alt='Photo',height=260,onError}:{uri:string;alt?:string;height?:number;onError?:()=>void}){
 const [open,setOpen]=useState(false),[failed,setFailed]=useState(false),size=useWindowDimensions();
 useEffect(()=>setFailed(false),[uri]);
 return <><Pressable accessibilityRole="button" accessibilityLabel={'Open photo: '+alt} onPress={()=>{setFailed(false);setOpen(true);}}><Image source={{uri}} accessibilityLabel={alt} onError={onError} style={{width:'100%',height,borderRadius:12}}/></Pressable><Modal visible={open} animationType="fade" presentationStyle="fullScreen" onRequestClose={()=>setOpen(false)}><SafeAreaView style={s.screen}><View style={[s.spread,{padding:16}]}><Text style={[s.label,{flex:1}]} numberOfLines={2}>{alt}</Text><Button secondary title="Close photo" onPress={()=>setOpen(false)}/></View><ScrollView style={{flex:1}} contentContainerStyle={{flexGrow:1,alignItems:'center',justifyContent:'center'}} minimumZoomScale={1} maximumZoomScale={5} centerContent>{failed?<Text style={s.error}>Photo unavailable. Close and refresh to try again.</Text>:<Image source={{uri}} accessibilityLabel={alt} resizeMode="contain" onError={()=>{setFailed(true);onError?.();}} style={{width:size.width,height:Math.max(200,size.height-150)}}/>}</ScrollView><Text style={[s.muted,{padding:16,textAlign:'center'}]}>Pinch to zoom</Text></SafeAreaView></Modal></>;
}
