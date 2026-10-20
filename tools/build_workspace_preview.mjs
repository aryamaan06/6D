import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const template = await fs.readFile(path.join(root, 'design/workspace-preview.source.html'), 'utf8');
const reference = JSON.parse(await fs.readFile(path.join(root, 'design/fixtures/workspace-reference.json'), 'utf8'));
const marker = '__SIXD_REFERENCE_JSON__';
if (template.split(marker).length !== 2) throw new Error('Expected one reference-data marker.');
const fragment = template.replace(marker, JSON.stringify(reference).replaceAll('<', '\\u003c'));
if (Buffer.byteLength(fragment) >= 1_000_000) throw new Error('Preview exceeds the inline size budget.');
await fs.writeFile(path.join(root, 'design/workspace-preview.fragment.html'), fragment, 'utf8');
console.log('Built design/workspace-preview.fragment.html from source and recorded reference data.');
