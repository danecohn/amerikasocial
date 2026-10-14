import {readFileSync,readdirSync,writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {join} from 'node:path';
import {parse} from '@babel/parser';
import traverse from '@babel/traverse';
import generate from '@babel/generator';
const directory=fileURLToPath(new URL('../src',import.meta.url));let problems=0;
for(const name of readdirSync(directory).filter(name=>name.endsWith('.tsx'))){const path=join(directory,name),source=readFileSync(path,'utf8'),ast=parse(source,{sourceType:'module',plugins:['typescript','jsx']});let changed=false;
 const outsideText=path=>{const parent=path.findParent(p=>p.isJSXElement());return !parent||parent.node.openingElement.name.type!=='JSXIdentifier'||parent.node.openingElement.name.name!=='Text';};
 traverse(ast,{JSXText(path){if(path.node.value&&!path.node.value.includes('\n')&&!path.node.value.trim()&&outsideText(path)){problems++;changed=true;if(process.argv.includes('--fix'))path.remove();}},JSXExpressionContainer(path){const e=path.node.expression;if(e.type==='StringLiteral'&&e.value.length&&!e.value.trim()&&outsideText(path)){problems++;changed=true;if(process.argv.includes('--fix'))path.remove();}}});
 if(changed&&process.argv.includes('--fix'))writeFileSync(path,generate(ast).code+'\n');
}
if(problems&&!process.argv.includes('--fix')){console.error('Found '+problems+' raw JSX whitespace nodes outside native Text. Run pnpm check:jsx --fix.');process.exitCode=1;}else console.log(process.argv.includes('--fix')?'Removed '+problems+' unsafe native JSX whitespace nodes.':'Native JSX text boundaries passed.');
