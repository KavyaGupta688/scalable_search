import React from 'react';
import { RESOLUTIONS, resolutionCounts } from '../services/facets';
import { FacetChoiceFilter } from './FacetChoiceFilter';

/** Photo and video resolution filter: 4K, 2K, Full HD, HD, Below HD (and Unknown when some are unmeasured). */
export const ResolutionFilter = ({ catalog, layout = 'chips' }) => {
  const counts = resolutionCounts(catalog.facets);
  const choices = counts && counts.unknown > 0
    ? [...RESOLUTIONS, { id: 'unknown', label: 'Unknown', hint: 'Photos or videos whose size has not been measured' }]
    : RESOLUTIONS;
  const measured = counts ? RESOLUTIONS.reduce((total, tier) => total + counts[tier.id], 0) : 0;
  const note = counts && measured === 0 && counts.unknown > 0
    ? `Resolution has not been measured for ${counts.unknown.toLocaleString()} photo/video file(s) yet.`
    : '';
  return <FacetChoiceFilter catalog={catalog} field="resolutions" title="Resolution" listTitle="Resolution (photos & videos)"
    choices={choices} counts={counts} layout={layout} note={note} />;
};
