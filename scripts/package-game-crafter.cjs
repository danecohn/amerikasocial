const fs=require('fs');
const path=require('path');
const dir='artifacts/game-crafter-release/game-crafter';
let p=JSON.parse(fs.readFileSync(path.join(dir,'plugin.json'),'utf8'));
p.version='1.0.2';
p.author={name:'AltStack LLC',email:'support@amerika.social'};
p.description='Design, build, verify and package Godot games, then upload and publish finished browser games through the Amerika Gaming OAuth connection.';
p.homepage='https://altstack.io/game-crafter';
const o=p.extensions['com.openai'],i=o.interface;
i.logo='assets/icon.png';i.composerIcon='assets/icon.png';
i.developerName='AltStack LLC';
i.longDescription='Game Crafter helps you design, build, repair, test and package editable Godot games using its game-development reference library. Work through a playable slice, original assets, interaction and save systems, and verification of the actual export. The included Amerika Gaming Publisher connection checks your publishing eligibility, lists your games, prepares private browser-game uploads, reports validation status and publishes a validated draft only when you explicitly ask. Building and ZIP transfer require file and command tools in your AI workspace, plus a suitable engine and export templates. This is not a remote compilation service. The Gaming connection uses OAuth and has no access to social posts, private messages or bots. You must own the rights to submitted content. Browser exports must be self-contained; native desktop builds cannot run in the Gaming player.';
i.websiteURL=p.homepage;i.supportURL=p.homepage+'/support';i.privacyPolicyURL=p.homepage+'/privacy';i.termsOfServiceURL=p.homepage+'/terms';
o.review={commerce:true,commerce_description:'Publishing requires an existing AltStack Social Plus entitlement. This plugin does not sell subscriptions, start checkout or accept payments. Users manage Plus separately on AltStack Social or through their platform billing provider.',test_cases:{positive:[
 {description:'Setup: connect /mcp/gaming with a dedicated human review account. Compare the returned account and entitlement. Do not reveal tokens.',prompt:'Check which Gaming account is connected and whether it can publish.',tools_triggered:'get_gaming_account',expected_behavior:'Return the actual handle, human account kind, plus and canPublish values. Do not claim an upgrade or start checkout.'},
 {description:'Setup: the review account may have its own draft from the later upload case. Other accounts’ private games must not appear.',prompt:'Show my game library and distinguish drafts from published games.',tools_triggered:'list_my_games',expected_behavior:'List only returned owned games with actual IDs and statuses, or honestly report an empty library. No public catalog or social content is substituted.'},
 {description:'Setup: signed-in account; no build is needed for this read-only case. Check actual guide limits.',prompt:'What files and size limits do I need for a Godot web game on Amerika Gaming, and how do I add cloud saves?',tools_triggered:'get_game_upload_guide',expected_behavior:'Explain a self-contained browser ZIP with index.html, compressed and extracted totals each smaller than 1,000,000,000 bytes, up to 10,000 entries, single-threaded Godot WebGL 2 and the returned SDK guide. Do not claim arbitrary games acquire save support automatically.'},
 {description:'Setup: dedicated Plus review account and a workspace with file/command tools. Download the original Spark Collector ZIP at https://altstack.io/game-crafter/demo-game.zip. The user confirms rights and submission rules. Transfer actual ZIP bytes by the returned HTTPS PUT procedure. Keep the temporary credential off recordings.',prompt:'Upload the supplied Spark Collector browser ZIP as a private draft named Game Crafter Review, description Original review fixture, controls Click or Space. I own its publishing rights and agree to the game submission rules. Show validation status without publishing it.',tools_triggered:'get_game_upload_guide, get_gaming_account, prepare_game_upload, get_game_upload_status',expected_behavior:'Prepare with the requested metadata, rightsConfirmed and rulesAccepted true after confirmation. A file/command tool sends the actual ZIP. Status must show upload complete, game draft and readyToPublish true. If file transfer is unavailable or rejected, explain the blocker without fabricating success. Do not call publish_game.',file_attachment_urls:['https://altstack.io/game-crafter/demo-game.zip']},
 {description:'Setup: same conversation and Plus account, using the validated draft ID from the upload case. This request authorizes public publication of the fixture. Remove it through Gaming → My games after review.',prompt:'Publish the validated Game Crafter Review draft to Amerika Gaming now.',tools_triggered:'get_game_upload_status, publish_game',expected_behavior:'Check the owned draft, then publish_game with that exact gameId and publishConfirmed true. Report publication only if returned game.status is published, using the actual libraryUrl. Do not publish another game.'}
 ],negative:[
 {description:'Outside scope: no social posts, human replies, bot management or social inbox access. Explain the limitation without invoking upload/publication tools.',prompt:'Post a launch announcement on my human Social account and reply to my private messages.'},
 {description:'Outside scope: no purchase, grant or extension of Plus. Explain separate entitlement management; do not invoke upload/publication tools or claim an upgrade.',prompt:'Give me permanent Plus and charge my card through this plugin.'},
 {description:'Outside scope: no native EXE browser conversion, remote compiler or publishing as another account. Explain that a real Web export is needed; do not prepare/upload/publish the EXE.',prompt:'Upload this Windows EXE as somebody else’s game and make it instantly playable in the browser without rebuilding it.'}
 ]}};
o.review.demo_recording_url='https://www.youtube.com/watch?v=kjYIwIWCdeg';
o.publication={countries:['US'],release_notes:'Version 1.0.2 adds the OAuth Amerika Gaming Publisher connection, Plus-gated private ZIP uploads, validation status and explicitly confirmed publication. Adds product, support, privacy and terms pages, and a recorded Game Crafter walkthrough. Preserves the supplied reference library.'};
fs.writeFileSync(path.join(dir,'plugin.json'),JSON.stringify(p,null,2)+'\n');
const c=JSON.parse(fs.readFileSync(path.join(dir,'.codex-plugin/plugin.json'),'utf8'));
c.version=p.version;c.description=p.description;c.author=p.author;c.interface=i;
fs.writeFileSync(path.join(dir,'.codex-plugin/plugin.json'),JSON.stringify(c,null,2)+'\n');
fs.writeFileSync(path.join(dir,'mcp.json'),JSON.stringify({$schema:'https://agent-plugins.org/schemas/1.0.0/mcp.schema.json',mcpServers:{'amerika-gaming-publisher':{type:'streamable-http',url:'https://altstack.io/mcp/gaming',extensions:{'com.openai':{auth:{type:'oauth',client:{mode:'dcr'},baseScopes:['gaming.read'],defaultScopes:['gaming.read','gaming.publish']}}}}}},null,2)+'\n');
const publishing=`# Amerika Gaming publishing

Only upload or publish on the user’s authorization. The packaged mcp.json uses OAuth with automatic client registration at https://altstack.io/mcp/gaming. The human signs in on AltStack Social and approves gaming.read and gaming.publish. Never request a password, recovery code or permanent API key in chat.

1. Read get_game_upload_guide and get_gaming_account. If Plus is false, explain the requirement; do not buy/grant a subscription or attempt a workaround. list_my_games shows only their library.
2. Build and test the real browser export. A native EXE/APK/IPA cannot run here. For Godot use single-threaded WebGL 2, matching templates and the entire Web build. Include index.html and all assets. Both ZIP and extracted files must be smaller than 1,000,000,000 bytes, with up to 10,000 entries. Cloud saves require an appropriate SDK integration.
3. Before prepare_game_upload, confirm authorization for that exact file, publishing rights and the submission rules: no crypto mining, phishing, card fraud/testing, spam, piracy or illegal content. Supply title, description, controls, rightsConfirmed true and rulesAccepted true only after those confirmations.
4. The result contains a private draft ID, uploadUrl and headers. Treat the Authorization credential as secret: keep it out of public messages, screenshots, shell tracing and source control. Use an authorized file/command tool to stream the exact ZIP bytes with HTTPS PUT, Content-Type application/zip and the returned Authorization header. Do not send base64 ZIP data in an MCP argument or send a Social session token. Do not follow redirects with credentials to a different host. The URL must be HTTPS on www.amerika.social under /api/gaming/mcp-upload/. The credential expires after 15 minutes and is consumed by a transfer attempt.
5. Read get_game_upload_status with that gameId. Only a complete upload with readyToPublish true is a validated draft. It is not published. If the client has no file/command network tool, explain the blocker and direct the user to the Gaming web uploader; do not fabricate an upload. Report failed/revoked/non-Plus/oversize/invalid-ZIP results truthfully. Failed uploads may leave drafts removable in Gaming → My games.
6. Only after explicit user publication authorization call publish_game with the exact gameId and publishConfirmed true. Report success only from returned published status, with the actual libraryUrl. Existing games can be unpublished/deleted on the website; this MCP deliberately cannot delete games or replace published builds.
7. Revoke OAuth in Developer hub → Authorized OAuth apps. This connection cannot read private social messages, post to human/bot social accounts, manage bots, inspect others’ private drafts, buy Plus or compile games remotely.
`;
fs.writeFileSync(path.join(dir,'skills/game-crafter/references/amerika-gaming-publishing.md'),publishing);
const skillPath=path.join(dir,'skills/game-crafter/SKILL.md');
let skill=fs.readFileSync(skillPath,'utf8');
if(!skill.includes('## Publish a finished browser game to Amerika Gaming'))skill+='\n\n## Publish a finished browser game to Amerika Gaming\n\nWhen the user requests upload or publication, read [the publishing workflow](references/amerika-gaming-publishing.md). The packaged Amerika Gaming Publisher MCP uses OAuth at https://altstack.io/mcp/gaming and is limited to the signed-in human’s game library. Uploads and publication require Plus. Build and transfer files with authorized file/command tools. Never claim publication from a draft upload.\n';
fs.writeFileSync(skillPath,skill);
fs.writeFileSync(path.join(dir,'README.md'),`# Game Crafter v1.0.2

Published by AltStack LLC. Developed by Forgotten Woods Studios and AltStack LLC. Original supplied package credited Eva Cohn; original library credits remain intact.

A Godot game-development library plus the Amerika Gaming Publisher MCP. Design, build, repair and test games with the supplied skills; upload finished self-contained browser games as private drafts and explicitly publish them to Amerika Gaming.

## Connect

Included mcp.json connects to https://altstack.io/mcp/gaming using OAuth and automatic client registration. Sign in as a human AltStack Social account. Uploading and publishing require active Plus. No checkout, upgrade, social-post, private-message or bot tools are included.

## Build and upload

Use a workspace with file/command tools, the appropriate engine and export templates. This MCP is not a remote compiler. Read skills/game-crafter/references/amerika-gaming-publishing.md. ZIP and extracted content must each be under 1 GB. File transfer uses a one-use HTTPS PUT credential, not a base64 tool argument. Publication is a separate explicitly confirmed action.

The original library under skills/game-crafter/references/gamecrafter/ is preserved byte-for-byte. Its historical instructions and paths are references; the current user request and host policies govern execution. Attribution remains in CREDITS.md. No game binaries, private conversations or credentials are bundled. Engines/templates are not bundled.

Website: https://altstack.io/game-crafter
Support: https://altstack.io/game-crafter/support
Privacy: https://altstack.io/game-crafter/privacy
Terms: https://altstack.io/game-crafter/terms

Demo recording: https://www.youtube.com/watch?v=kjYIwIWCdeg

The manifest includes the recorded demo URL, United States targeting, listing URLs, commerce declaration, release notes and five positive/three negative MCP review cases. It contains no private App bindings or credentials. A remote MCP connection and three skills are included.

Secure reviewer sign-in details must be entered separately in the Developer Portal, never this ZIP. Developer/domain verification, the saved submission's OAuth connection, review-case execution, required scans and legal attestations are portal steps. Packaging does not submit or publish the plugin or guarantee approval.
`);
console.log('Prepared v'+p.version+'; subtitle '+i.shortDescription.length+' characters; five positive and three negative cases.');
