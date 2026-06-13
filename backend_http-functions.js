import { ok, badRequest, serverError } from 'wix-http-functions';
import wixData from 'wix-data';
import { rollPackItems } from 'backend/packItems.js';

const COLLECTION = 'Import2';
const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type'
};

export function options_getItems()          { return ok({ headers: CORS }); }
export function options_getOpenedMints()    { return ok({ headers: CORS }); }
export function options_openPack()          { return ok({ headers: CORS }); }
export function options_getOrCreateProfile(){ return ok({ headers: CORS }); }
export function options_adminSearch()       { return ok({ headers: CORS }); }
export function options_adminSave()         { return ok({ headers: CORS }); }
export function options_adminDelete()       { return ok({ headers: CORS }); }
export function options_adminGrantPack()    { return ok({ headers: CORS }); }

// Finds a profile row by wallet address (checks solanaWallet and tezosWallet)
async function findByWallet(wallet) {
  const [bySol, byTez] = await Promise.all([
    wixData.query(COLLECTION).eq('solanaWallet', wallet).find(),
    wixData.query(COLLECTION).eq('tezosWallet',  wallet).find()
  ]);
  return bySol.items[0] || byTez.items[0] || null;
}

const ADMIN_SECRET = 'hex-admin-2026';

function adminAuth(secret) {
  return secret === ADMIN_SECRET;
}

// POST /adminSearch  { secret, query }
export async function post_adminSearch(request) {
  try {
    const { secret, query } = await request.body.json();
    if (!adminAuth(secret)) return badRequest({ headers: CORS, body: { error: 'unauthorized' } });
    if (!query) return badRequest({ headers: CORS, body: { error: 'query required' } });

    const q = query.trim();
    const [bySol, byTez, byName] = await Promise.all([
      wixData.query(COLLECTION).contains('solanaWallet', q).find(),
      wixData.query(COLLECTION).contains('tezosWallet', q).find(),
      wixData.query(COLLECTION).contains('witchname', q).find()
    ]);

    const seen = new Set();
    const results = [];
    for (const row of [...bySol.items, ...byTez.items, ...byName.items]) {
      if (!seen.has(row._id)) {
        seen.add(row._id);
        results.push({
          _id: row._id,
          witchname: row.witchname || '',
          solanaWallet: row.solanaWallet || '',
          tezosWallet: row.tezosWallet || '',
          items: Array.isArray(row.items) ? row.items : [],
          openedMints: Array.isArray(row.openedMints) ? row.openedMints : [],
          slots: Array.isArray(row.slots) ? row.slots : []
        });
      }
    }
    return ok({ headers: CORS, body: { results } });
  } catch (e) {
    return serverError({ headers: CORS, body: { error: e.message } });
  }
}

// POST /adminSave  { secret, _id, witchname, solanaWallet, tezosWallet, items, openedMints }
export async function post_adminSave(request) {
  try {
    const { secret, _id, witchname, solanaWallet, tezosWallet, items, openedMints } = await request.body.json();
    if (!adminAuth(secret)) return badRequest({ headers: CORS, body: { error: 'unauthorized' } });
    if (!_id) return badRequest({ headers: CORS, body: { error: '_id required' } });

    const result = await wixData.query(COLLECTION).eq('_id', _id).find();
    const existing = result.items[0];
    if (!existing) return badRequest({ headers: CORS, body: { error: 'record not found' } });

    await wixData.update(COLLECTION, {
      ...existing,
      witchname: witchname ?? existing.witchname,
      solanaWallet: solanaWallet ?? existing.solanaWallet,
      tezosWallet: tezosWallet ?? existing.tezosWallet,
      items: Array.isArray(items) ? items : existing.items,
      openedMints: Array.isArray(openedMints) ? openedMints : existing.openedMints
    }, { suppressAuth: true });

    return ok({ headers: CORS, body: { success: true } });
  } catch (e) {
    return serverError({ headers: CORS, body: { error: e.message } });
  }
}

// POST /adminDelete  { secret, _id }
export async function post_adminDelete(request) {
  try {
    const { secret, _id } = await request.body.json();
    if (!adminAuth(secret)) return badRequest({ headers: CORS, body: { error: 'unauthorized' } });
    if (!_id) return badRequest({ headers: CORS, body: { error: '_id required' } });

    await wixData.remove(COLLECTION, _id, { suppressAuth: true });
    return ok({ headers: CORS, body: { success: true } });
  } catch (e) {
    return serverError({ headers: CORS, body: { error: e.message } });
  }
}

// POST /adminGrantPack  { secret, _id, rarity, count }
export async function post_adminGrantPack(request) {
  try {
    const { secret, _id, rarity, count } = await request.body.json();
    if (!adminAuth(secret)) return badRequest({ headers: CORS, body: { error: 'unauthorized' } });
    if (!_id || !rarity) return badRequest({ headers: CORS, body: { error: '_id and rarity required' } });

    const result = await wixData.query(COLLECTION).eq('_id', _id).find();
    const existing = result.items[0];
    if (!existing) return badRequest({ headers: CORS, body: { error: 'record not found' } });

    const ownedPaths = Array.isArray(existing.items) ? [...existing.items] : [];
    const grantCount = Math.max(1, Math.min(10, count || 1));
    const granted = [];

    for (let i = 0; i < grantCount; i++) {
      const rolled = rollPackItems(rarity, ownedPaths);
      rolled.forEach(item => {
        if (!ownedPaths.includes(item.path)) {
          ownedPaths.push(item.path);
          granted.push(item);
        }
      });
    }

    await wixData.update(COLLECTION, { ...existing, items: ownedPaths }, { suppressAuth: true });
    return ok({ headers: CORS, body: { success: true, granted, totalItems: ownedPaths.length } });
  } catch (e) {
    return serverError({ headers: CORS, body: { error: e.message } });
  }
}

const PREFIXES = ['ShadowWitch','CursedSoul','DarkRitual','HexMaster','VoidCaster',
                  'BloodMoon','GrimWeaver','BoneCaller','NightHag','RuneKeeper'];

// POST /getOrCreateProfile
// Body: { wallet, platform }  — platform: 'sol' | 'tez'
export async function post_getOrCreateProfile(request) {
  try {
    const { wallet, platform } = await request.body.json();
    if (!wallet || !platform) return badRequest({ headers: CORS, body: { error: 'wallet and platform required' } });

    const walletField = platform === 'tez' ? 'tezosWallet' : 'solanaWallet';

    // Look up by wallet address
    const existing = await wixData.query(COLLECTION).eq(walletField, wallet).find();
    if (existing.items.length > 0) {
      const row = existing.items[0];
      return ok({ headers: CORS, body: {
        witchName: row.witchname,
        solanaWallet: row.solanaWallet || null,
        tezosWallet: row.tezosWallet || null,
        items: Array.isArray(row.items) ? row.items : [],
        isNew: false
      }});
    }

    // New profile — get next sequential number
    const configRes = await wixData.query('Config').eq('key', 'lastProfileNumber').find();
    const configRow = configRes.items[0];
    const nextNum = (configRow.value || 0) + 1;
    const padded = String(nextNum).padStart(4, '0');
    const prefix = PREFIXES[nextNum % PREFIXES.length];
    const witchName = `${prefix}#${padded}`;

    // Save updated counter
    await wixData.update('Config', { ...configRow, value: nextNum }, { suppressAuth: true });

    // Create new profile
    const newRow = { [walletField]: wallet, witchname: witchName, items: [], openedMints: [] };
    await wixData.insert(COLLECTION, newRow, { suppressAuth: true });

    return ok({ headers: CORS, body: {
      witchName,
      solanaWallet: platform === 'sol' ? wallet : null,
      tezosWallet: platform === 'tez' ? wallet : null,
      items: [],
      isNew: true
    }});
  } catch (e) {
    return serverError({ headers: CORS, body: { error: e.message } });
  }
}

// GET /getItems?wallet=xxx
export async function get_getItems(request) {
  const wallet = request.query.wallet;
  if (!wallet) return badRequest({ headers: CORS, body: { error: 'wallet required' } });

  try {
    const row = await findByWallet(wallet);
    const items = (row && Array.isArray(row.items)) ? row.items : [];
    return ok({ headers: CORS, body: { items } });
  } catch (e) {
    return serverError({ headers: CORS, body: { error: e.message } });
  }
}

// GET /getOpenedMints?wallet=xxx
export async function get_getOpenedMints(request) {
  const wallet = request.query.wallet;
  if (!wallet) return badRequest({ headers: CORS, body: { error: 'wallet required' } });

  try {
    const row = await findByWallet(wallet);
    const mints = (row && Array.isArray(row.openedMints)) ? row.openedMints : [];
    return ok({ headers: CORS, body: { mints } });
  } catch (e) {
    return serverError({ headers: CORS, body: { error: e.message } });
  }
}

// POST /openPack
// Body: { wallet, rarity, mintAddress }
export async function post_openPack(request) {
  try {
    const body = await request.body.json();
    const { wallet, rarity, mintAddress } = body;

    if (!wallet || !rarity) {
      return badRequest({ headers: CORS, body: { error: 'wallet and rarity required' } });
    }

    const existing = await findByWallet(wallet);

    // Double-open check
    if (existing && mintAddress) {
      const openedMints = Array.isArray(existing.openedMints) ? existing.openedMints : [];
      if (openedMints.includes(mintAddress)) {
        return badRequest({ headers: CORS, body: { error: 'pack already opened' } });
      }
    }

    // Sahip olunan item'ları al, roll'dan çıkar
    const ownedPaths = existing && Array.isArray(existing.items) ? existing.items : [];
    const rolledItems = rollPackItems(rarity, ownedPaths);

    // Koleksiyon tamamsa
    if (rolledItems.length === 0) {
      return ok({ headers: CORS, body: { success: true, items: [], message: 'collection complete' } });
    }

    const itemPaths = rolledItems.map(i => i.path);

    if (existing) {
      const mergedItems = [...ownedPaths];
      itemPaths.forEach(i => { if (!mergedItems.includes(i)) mergedItems.push(i); });

      const openedMints = Array.isArray(existing.openedMints) ? existing.openedMints : [];
      const mergedMints = [...openedMints];
      if (mintAddress && !mergedMints.includes(mintAddress)) mergedMints.push(mintAddress);

      await wixData.update(COLLECTION, {
        ...existing,
        items: mergedItems,
        openedMints: mergedMints,
        rarity,
        openedAt: new Date()
      });
    } else {
      await wixData.insert(COLLECTION, {
        wallet,
        rarity,
        openedMints: mintAddress ? [mintAddress] : [],
        items: itemPaths,
        openedAt: new Date()
      });
    }

    return ok({ headers: CORS, body: { success: true, items: rolledItems } });
  } catch (e) {
    return serverError({ headers: CORS, body: { error: e.message } });
  }
}

export function options_getSlots()  { return ok({ headers: CORS }); }
export function options_saveSlots() { return ok({ headers: CORS }); }

export async function get_getSlots(request) {
  const wallet = request.query.wallet;
  if (!wallet) return badRequest({ headers: CORS, body: { error: 'wallet required' } });
  try {
    const row = await findByWallet(wallet);
    const slots = (row && Array.isArray(row.slots)) ? row.slots : [null, null, null, null];
    return ok({ headers: CORS, body: { slots } });
  } catch (e) {
    return serverError({ headers: CORS, body: { error: e.message } });
  }
}

export async function post_saveSlots(request) {
  try {
    const body = await request.body.json();
    const { wallet, slots } = body;
    if (!wallet || !slots) return badRequest({ headers: CORS, body: { error: 'wallet and slots required' } });
    const existing = await findByWallet(wallet);
    if (existing) {
      await wixData.update(COLLECTION, { ...existing, slots });
    } else {
      await wixData.insert(COLLECTION, { solanaWallet: wallet, slots, items: [], openedMints: [], openedAt: new Date() });
    }
    return ok({ headers: CORS, body: { success: true } });
  } catch (e) {
    return serverError({ headers: CORS, body: { error: e.message } });
  }
}

export function options_getLeaderboard() { return ok({ headers: CORS }); }

export async function get_getLeaderboard(request) {
  try {
    const result = await wixData.query(COLLECTION).limit(1000).find();
    const entries = result.items.map(row => {
      const slot = Array.isArray(row.slots) && row.slots[0];
      const items = (slot && slot.equipped)
        ? Object.values(slot.equipped).filter(v => v && typeof v === 'string')
        : [];
      let curse = 0, doom = 0, hex = 0;
      items.forEach(path => {
        const filename = path.split('/').pop();
        const rarity = path.split('/')[1] || 'common';
        const TOTALS = { common: 15, rare: 40, legendary: 90, ultimate: 180 };
        const total = TOTALS[rarity] || 15;
        let h = 5381;
        for (let i = 0; i < filename.length; i++) h = ((h << 5) + h + filename.charCodeAt(i)) | 0;
        h = Math.abs(h);
        const a = 1 + (h % 7);
        const b = 1 + ((h >>> 4) % 7);
        const c = 1 + ((h >>> 8) % 7);
        const sum = a + b + c;
        curse += Math.round(total * a / sum);
        doom  += Math.round(total * b / sum);
        hex   += total - Math.round(total * a / sum) - Math.round(total * b / sum);
      });
      const power = curse + doom + hex;
      return { wallet: row.wallet, curse, doom, hex, power };
    });
    return ok({ headers: CORS, body: { entries } });
  } catch (e) {
    return serverError({ headers: CORS, body: { error: e.message } });
  }
}
