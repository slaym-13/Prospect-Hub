import { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import './map.css';
import { STATUS_LABEL } from '../../lib/format';

/*
 * This module (and Leaflet with it) is only downloaded when someone opens the map.
 * All markers are drawn on one canvas rather than as hundreds of DOM elements, so
 * panning and zooming stay smooth however many companies are on it.
 */

const MARRAKECH = [31.6295, -7.9811];
// OpenStreetMap's own tiles: free with attribution and no key. map.css tones them
// down to the app's palette (and inverts them in dark mode).
const TILES = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

/** Status → theme token, so the pins follow light and dark like the rest of the app. */
const TOKEN = {
  new: '--muted',
  contacted: '--accent',
  replied: '--accent',
  meeting: '--accent',
  won: '--good',
  lost: '--bad',
  optout: '--bad'
};
export const LEGEND = [
  ['Not contacted', '--neutral'],
  ['In progress', '--accent'],
  ['Won', '--good'],
  ['Lost or opted out', '--bad']
];

const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

export default function CompaniesMap({ leads, onOpen }) {
  const boxRef = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);
  const openRef = useRef(onOpen);
  openRef.current = onOpen;
  const pointsRef = useRef([]);
  const framedRef = useRef(false);

  // The map itself: made once, removed when the page closes.
  useEffect(() => {
    const map = L.map(boxRef.current, {
      center: MARRAKECH,
      zoom: 12,
      preferCanvas: true,
      zoomSnap: 0.25, // fit the pins snugly instead of jumping a whole zoom level
      zoomDelta: 0.5,
      zoomControl: true,
      attributionControl: true,
      scrollWheelZoom: true
    });
    L.tileLayer(TILES, {
      maxZoom: 19,
      attribution: ATTRIBUTION,
      detectRetina: false,
      // The app sends no Referer anywhere, but OpenStreetMap's usage policy asks for
      // one. Tiles alone send the site's origin (never the page's path).
      referrerPolicy: 'strict-origin'
    }).addTo(map);
    layerRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;

    // Follow the app's theme switch: the tiles follow through CSS, the pins are recoloured.
    const watch = new MutationObserver(() => {
      layerRef.current.eachLayer((m) => m.setStyle(style(m.options.status)));
    });
    watch.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });

    // Leaflet measures its box once. The box gets its real size a moment later (the page
    // is still arriving), so measure again on every resize, and frame the pins the first
    // time there is room to.
    const sized = new ResizeObserver(() => {
      if (!boxRef.current?.clientHeight) return;
      map.invalidateSize({ pan: false });
      if (!framedRef.current) frame();
    });
    sized.observe(boxRef.current);

    return () => {
      sized.disconnect();
      watch.disconnect();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // The pins: redrawn when the filters change the list, then framed.
  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map) return;
    layer.clearLayers();
    const points = [];
    // Best leads last, so they are drawn on top where pins overlap.
    const placed = leads.filter((l) => Number.isFinite(l.latitude) && Number.isFinite(l.longitude));
    placed.sort((a, b) => (a.score || 0) - (b.score || 0));
    for (const l of placed) {
      const at = [l.latitude, l.longitude];
      points.push(at);
      L.circleMarker(at, { ...style(l.status), radius: 4 + Math.round((l.score || 0) / 22), status: l.status })
        .bindTooltip(`<strong>${escape(l.nom)}</strong><br>${escape(l.categorie || '')} · ${STATUS_LABEL[l.status]}`, {
          direction: 'top',
          offset: [0, -6],
          className: 'ph-tip'
        })
        .on('click', () => openRef.current(l.id))
        .addTo(layer);
    }
    pointsRef.current = points;
    framedRef.current = false;
    frame();
  }, [leads]);

  function frame() {
    const map = mapRef.current;
    if (!map || !boxRef.current?.clientHeight) return;
    if (pointsRef.current.length) map.fitBounds(pointsRef.current, { padding: [36, 36], maxZoom: 15, animate: false });
    framedRef.current = true;
  }

  return <div ref={boxRef} className="relative z-0 h-full w-full" aria-label="Map of the companies" role="region" />;
}

function style(status) {
  const color = css(TOKEN[status] || '--neutral');
  return { color: css('--surface'), weight: 1.5, fillColor: color, fillOpacity: 0.9 };
}

function escape(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
}
