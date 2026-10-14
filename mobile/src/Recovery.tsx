import React from 'react';
import {Text} from 'react-native';
import {ApiForm,Page} from './ui';
import {Button} from './components';
import {styles as s} from './theme';
export default function Recovery({onBack}:{onBack:()=>void}){return <Page title="Recover your account" onClose={onBack}><Text style={s.text}>Use one of your saved, single-use recovery codes. This replaces your password and revokes previous sessions and credentials. No email is needed.</Text><ApiForm path="recovery/reset" fields={[{key:'handle',label:'Username',max:253},{key:'code',label:'Saved recovery code',type:'password',max:100},{key:'password',label:'New password (10–256 characters)',type:'password',max:256}]} submit="Reset password"/><Button secondary title="Back to sign in" onPress={onBack}/></Page>;}
