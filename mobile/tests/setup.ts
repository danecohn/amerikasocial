jest.mock('react-native-safe-area-context',()=>{const React=require('react'),{View}=require('react-native');return {SafeAreaProvider:({children}:any)=>React.createElement(View,null,children),SafeAreaView:View,useSafeAreaInsets:()=>({top:0,bottom:0,left:0,right:0})};});
jest.mock('@expo/vector-icons',()=>({Ionicons:()=>null}));
jest.mock('expo-video',()=>{const {View}=require('react-native');return {VideoView:View,useVideoPlayer:()=>({addListener:()=>({remove:()=>{}}),replaceAsync:jest.fn()})};});
jest.mock('react-native-webview',()=>({WebView:require('react-native').View}));
jest.mock('expo-clipboard',()=>({setStringAsync:jest.fn().mockResolvedValue(undefined)}));
jest.mock('expo-constants',()=>({__esModule:true,default:{executionEnvironment:'storeClient'}}));
jest.mock('../src/activity',()=>({nativePushAvailable:false,notificationActivity:jest.fn()}));
jest.mock('../src/device',()=>({profilePhoto:jest.fn(),deviceLocation:jest.fn(),upload:jest.fn(),exportPost:jest.fn().mockResolvedValue(undefined)}));
jest.mock('expo-notifications',()=>({setNotificationHandler:jest.fn(),getLastNotificationResponseAsync:jest.fn().mockResolvedValue(null),clearLastNotificationResponseAsync:jest.fn().mockResolvedValue(undefined),addNotificationResponseReceivedListener:()=>({remove:()=>{}})}));
