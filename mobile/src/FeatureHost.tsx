import React from 'react';
import {Actor} from './api';
import {Draft,Route} from './components';
import {Page} from './ui';
import DeveloperHub from './DeveloperHub';
import Communities from './Communities';
import Dating from './Dating';
import Moderation from './Moderation';
import Account from './Account';
import Explore from './Explore';
export type Feature='developers'|'communities'|'dating'|'moderation'|'account'|'explore';
export default function FeatureHost({feature,me,onClose,open,compose,onUpdated,onDeleted,initialThread}:{feature:Feature;me:Actor;onClose:()=>void;open:(route:Route)=>void;compose:(draft:Draft)=>void;onUpdated:()=>Promise<void>;onDeleted:()=>void;initialThread?:number}){
 const titles:Record<Feature,string>={developers:'Developer hub',communities:'AltStack Communities',dating:'AltStack Dating',moderation:'Moderation & administration',account:'Account settings',explore:'Discover & hashtags'};
 return <Page title={titles[feature]} onClose={onClose} onRefresh={onUpdated}>{feature==='developers'?<DeveloperHub me={me}/>:feature==='communities'?<Communities me={me} open={open} compose={compose}/>:feature==='dating'?<Dating me={me} initialThread={initialThread}/>:feature==='moderation'?<Moderation me={me} open={open} compose={compose}/>:feature==='account'?<Account me={me} onUpdated={onUpdated} onDeleted={onDeleted}/>:<Explore me={me} open={open} compose={compose}/>}</Page>;
}
