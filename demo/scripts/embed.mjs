import fs from 'node:fs/promises';
const assets={};for(const name of ['index.html','demo.html','record.js','record-template.js','demo.js','records.html'])assets[name]=await fs.readFile(new URL('../public/'+name,import.meta.url),'utf8');
const server=await fs.readFile(new URL('../worker/server.js',import.meta.url),'utf8');
await fs.writeFile(new URL('../worker/index.js',import.meta.url),server+'\nconst assets='+JSON.stringify(assets)+';\nexport default createHandler(assets);\n');
