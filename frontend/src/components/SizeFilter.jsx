import React from 'react';
import { SIZES, sizeCounts } from '../services/sizes';
import { FacetChoiceFilter } from './FacetChoiceFilter';

/** File-size filter by bucket (Under 100 KB ... 1 GB and larger), with counts. */
export const SizeFilter = ({ catalog, layout = 'chips' }) => (
  <FacetChoiceFilter catalog={catalog} field="size_buckets" title="File size" listTitle="File size"
    choices={SIZES} counts={sizeCounts(catalog.facets)} layout={layout} />
);
