#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import json
import logging
import re
from csv import DictWriter
from sys import exit

import click

logger = logging.getLogger(__name__)

# DBpedia ontology type URI for generic places
PLACE_TYPE = 'http://dbpedia.org/ontology/Place'

def prepare_crowdflower_input(sentences, frame_data, filter_places):
    data_units = []
    for sentence in sentences:
        logger.debug("Converting sentence item into CrowdFlower data unit: %s" % sentence)
        lu = sentence['lu']
        sentence_id = sentence['id']
        # Mint a CrowdFlower data unit upon sentence data
        data_unit = {
            'id': str(sentence_id),
            'sentence': sentence['text'],
            'lu': lu
        }
        linked_entities = sentence.get('linked_entities')
        if not linked_entities:
            logger.debug("No linked entities for sentence #%d. Skipping ..." % sentence_id)
            continue
        if filter_places:
            chunks = []
            for entity in linked_entities:
                chunk = entity['chunk']
                if PLACE_TYPE in entity['types']:
                    logger.debug("Filtered place (type '%s'): %s" % (PLACE_TYPE, chunk))
                    continue
                chunks.append(chunk)
        else:
            chunks = [entity['chunk'] for entity in linked_entities]
        if not chunks:
            logger.debug("No chunks for sentence #%d. Skipping ..." % sentence_id)
            continue
        logger.debug('Unit ID: %s' % data_unit['id'])
        logger.debug('Unit sentence: %s' % data_unit['sentence'])
        logger.debug('Unit LU: %s' % data_unit['lu'])
        logger.debug('Unit chunks: %s' % chunks)
        frame = frame_data.get(lu)
        if not frame:
            logger.warn("No frame data available for LU '%s'. Skipping ..." % lu)
            continue
        data_unit['frame'] = frame['frame']
        # Annotate both core and extra FEs
        fes = frame['core_fes'] + frame['extra_fes']
        for i, fe in enumerate(fes):
            data_unit['fe_%02d' % i] = fe['fe'].replace('_', ' ')
        for j, chunk in enumerate(chunks):
            data_unit['chunk_%02d' % j] = chunk
        logger.debug('Data unit completed: %s' % data_unit)
        # Prepare input for DictWriter, since it won't write UTF-8
        data_units.append({k: v.encode('utf-8') for k, v in data_unit.items()})
    return data_units


def write_input_spreadsheet(data_units, outfile):
    # Merge all the keys to prepare the CSV headers
    headers = set([k for d in data_units for k in d.keys()])
    # Specific field for test (gold) units
    headers.add('_golden')
    headers = list(headers)
    gold_columns = []
    for header in headers:
        # Add gold answer columns for each chunk
        if re.search('chunk_[0-9]{2}$', header):
            gold_columns.append(header + '_gold')
    headers += gold_columns
    headers.sort()
    logger.debug('CSV headers: %s' % headers)
    writer = DictWriter(outfile, headers)
    writer.writeheader()
    writer.writerows(data_units)
    return 0


@click.command()
@click.argument('frame_data', type=click.File())
@click.argument('sentences_data', type=click.File())
@click.option('--filter-places', '-f', is_flag=True, default=False)
@click.option('--outfile', '-o', type=click.File('w'), default='output/crowdflower_input.csv')
def main(frame_data, sentences_data, outfile, filter_places):
    """ Build the CSV input data for a CrowdFlower annotation job """
    if filter_places:
        logger.info("Will filter chunks that are typed as places ...")
    logger.info("Loading frame data from '%s' ..." % frame_data.name)
    frames = json.load(frame_data)
    # Need to keep all sentences data in memory, as we need them to shape the CSV
    sentences = []
    logger.info("Loading sentences data from '%s ..." % sentences_data.name)
    for line in sentences_data:
        sentence = json.loads(line)
        sentences.append(sentence)
    data_units = prepare_crowdflower_input(sentences, frames, filter_places)
    logger.info("Writing CrowdFlower data units CSV to '%s' ..." % outfile.name)
    write_input_spreadsheet(data_units, outfile)
    return 0


if __name__ == '__main__':
    exit(main())
