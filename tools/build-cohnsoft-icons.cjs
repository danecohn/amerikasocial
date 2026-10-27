// Original product artwork, authored as SVG geometry and exported through the Cohnsoft Sprite document/PNG engine.
// Company artwork in public/brand/cohnsoft is never modified.
const fs=require('node:fs'),path=require('node:path'),sharp=require('sharp');
const engine=process.env.COHN_SPRITE_ENGINE||path.resolve('../cohnsoftassets/tools/sprite');
const {Doc}=require(path.join(engine,'model.js')),{Session}=require(path.join(engine,'session.js')),Tools=require(path.join(engine,'tools.js'));
const symbols={
 search:'<circle cx="58" cy="55" r="22"/><path d="m74 72 18 18"/>',
 lookout:'<path d="m83 34-13 36-36 13 13-36Z"/><path d="m70 70-23-23"/><circle cx="58" cy="58" r="4"/>',
 office:'<path d="M43 28h31l13 14v53H43Z"/><path d="M74 28v17h13M53 58h24M53 69h24M53 80h16M33 39v65h45"/>',
 warehouse:'<path d="M31 51h66v42H31Z"/><path d="m31 51 10-21h46l10 21M43 66h42M51 79h26"/>',
 mail:'<rect x="29" y="38" width="70" height="51" rx="8"/><path d="m31 42 33 26 33-26M31 87l23-22M97 87 74 65"/>',
 calendar:'<rect x="32" y="31" width="64" height="66" rx="9"/><path d="M32 48h64M47 26v14M81 26v14M45 62h8M61 62h8M77 62h8M45 77h8M61 77h8"/>',
 social:'<path d="M31 36h52v37H58L43 85V73H31Z"/><path d="M84 49h13v39H82L68 99V88H61M43 49h27M43 60h18"/>',
 mind:'<path d="M34 31h45a12 12 0 0 1 12 12v53H46a12 12 0 0 1-12-12Z"/><path d="M46 31v65M59 51h19M59 63h19M59 75h12"/><circle cx="85" cy="30" r="8"/>',
 prompter:'<rect x="25" y="28" width="29" height="25" rx="5"/><rect x="75" y="75" width="29" height="25" rx="5"/><rect x="25" y="78" width="29" height="25" rx="5"/><path d="M54 40h20q15 0 15 15v20M39 53v25M54 90h21"/>',
 journal:'<path d="M27 35q19-6 37 4 18-10 37-4v57q-19-6-37 4-18-10-37-4ZM64 39v57"/><path d="M76 55c-9-9-15 6 6 19 21-13 15-28 6-19l-6 6Z"/>',
 gameproducer:'<rect x="27" y="48" width="74" height="49" rx="6"/><path d="M27 48v-9l70-17 4 17ZM43 35l9 11M63 30l9 11M83 25l9 11M54 61l23 13-23 13Z"/>',
 sprite:'<path d="M31 29h50v17H64v17H47v17H30ZM47 80h17v17H47ZM81 46h17v17H81ZM64 63h17v17H64Z"/><path d="M85 84v15M78 92h15"/>',
 box:'<path d="M34 78V39l49-10v39M34 49l49-10"/><ellipse cx="25" cy="80" rx="10" ry="7"/><ellipse cx="74" cy="70" rx="10" ry="7"/><path d="M97 64v34M89 85h16"/>',
 engine:'<path d="m64 25 34 20v40l-34 20-34-20V45ZM30 45l34 20 34-20M64 65v40M47 35l34 20v39"/>',
 render:'<path d="m64 24 39 72H25ZM64 24l15 72M64 24 48 96M25 96l39-23 39 23M48 96l16-23 15 23"/>',
 venture:'<circle cx="64" cy="64" r="35"/><path d="m81 42-9 30-30 9 9-30ZM29 64h12M87 64h12M64 29v12M64 87v12"/>',
 os:'<rect x="25" y="29" width="78" height="65" rx="8"/><path d="M25 45h78M46 45v49M34 37h2M44 37h2M58 58h32M58 70h24M58 82h17"/>',
};
(async()=>{for(const [name,shape]of Object.entries(symbols)){
 const svg=`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128"><defs><linearGradient id="tile" x2="0" y2="1"><stop stop-color="#9cf0bb"/><stop offset=".42" stop-color="#25bb5d"/><stop offset="1" stop-color="#0b6a34"/></linearGradient><linearGradient id="shine" x2="0" y2="1"><stop stop-color="#ffffff" stop-opacity=".55"/><stop offset="1" stop-color="#ffffff" stop-opacity="0"/></linearGradient><linearGradient id="glyph" x2="0" y2="1"><stop stop-color="#ffffff"/><stop offset="1" stop-color="#c8f6d9"/></linearGradient></defs><rect x="14" y="17" width="100" height="100" rx="25" fill="#05361b" opacity=".3"/><rect x="14" y="12" width="100" height="100" rx="25" fill="url(#tile)" stroke="#0b6a34" stroke-opacity=".5"/><rect x="15" y="13" width="98" height="96" rx="24" fill="none" stroke="url(#shine)" stroke-width="1.5"/><path d="M20 49q44 16 88-6V36q0-18-21-18H40q-19 0-20 18Z" fill="url(#shine)" opacity=".26"/><g transform="translate(9 7) scale(.86)" fill="none" stroke="url(#glyph)" stroke-width="3.8" stroke-linecap="round" stroke-linejoin="round">${shape}</g></svg>`;
 fs.writeFileSync('brand/product-icons/'+name+'.svg',svg);
 const {data}=await sharp(Buffer.from(svg)).resize(128,128).ensureAlpha().raw().toBuffer({resolveWithObject:true});
 const doc=Doc.fromRGBA(128,128,[{rgba:data,delay:100}]);doc.name='Cohnsoft '+name+' product icon';
 fs.writeFileSync('brand/product-icons/'+name+'.asprite.json',JSON.stringify(doc.toJSON()));
 await Tools.run(new Session(doc),'export',{format:'png',path:'public/brand/products/'+name+'.png'},{write:async(file,bytes)=>{fs.writeFileSync(file,Buffer.from(bytes));return {path:file}}});
 }console.log('Created '+Object.keys(symbols).length+' original product icons with editable Cohnsoft Sprite documents.');})().catch(e=>{console.error(e);process.exitCode=1});
