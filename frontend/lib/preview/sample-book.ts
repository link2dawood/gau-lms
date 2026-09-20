/**
 * Sample content for the interface preview (`/preview`).
 *
 * Nothing here reaches a production code path. It exists so the reading, search,
 * faculty and CMS screens can be reviewed before the content API (task 2.6) and
 * the textbook import (task 3.13) exist. The clinical text is illustrative
 * standard adult ranges written for layout purposes and has not been through
 * clinical review — it is not the GAU textbook.
 */

import type { ContentDocument, TocNode } from '@/lib/content/types';
import { bold, bulletList, callout, heading, paragraph, table, text } from '@/utils/tiptap';

// --- Table of contents ------------------------------------------------------

const leaf = (id: string, number: string, title: string): TocNode => ({
  id,
  type: 'SECTION',
  number,
  title,
  children: [],
});

export const SAMPLE_BOOK = {
  id: '5b1d0c7e-4a61-4c2e-9f0a-2d8e6b3c1a90',
  title: 'Professional Nursing Practice',
  course: { code: 'NURS 201', title: 'Fundamentals of Nursing Practice' },
} as const;

export const SAMPLE_TOC: readonly TocNode[] = [
  {
    id: 'u1',
    type: 'UNIT',
    number: '1',
    title: 'Foundations of nursing',
    children: [
      { id: 'c1', type: 'CHAPTER', number: '1', title: 'The profession of nursing', children: [] },
      { id: 'c2', type: 'CHAPTER', number: '2', title: 'Ethics and professional standards', children: [] },
      { id: 'c3', type: 'CHAPTER', number: '3', title: 'Communication in care', children: [] },
    ],
  },
  {
    id: 'u2',
    type: 'UNIT',
    number: '2',
    title: 'Assessment and clinical judgement',
    children: [
      { id: 'c4', type: 'CHAPTER', number: '4', title: 'The nursing process', children: [] },
      { id: 'c5', type: 'CHAPTER', number: '5', title: 'Health history and interview', children: [] },
      {
        id: 'c6',
        type: 'CHAPTER',
        number: '6',
        title: 'Vital signs',
        children: [
          leaf('s61', '6.1', 'Body temperature'),
          leaf('s62', '6.2', 'Pulse'),
          leaf('s63', '6.3', 'Respiration'),
          leaf('s64', '6.4', 'Blood pressure'),
          leaf('s65', '6.5', 'Oxygen saturation'),
        ],
      },
      { id: 'c7', type: 'CHAPTER', number: '7', title: 'Physical examination', children: [] },
    ],
  },
  {
    id: 'u3',
    type: 'UNIT',
    number: '3',
    title: 'Safe and effective care',
    children: [
      { id: 'c8', type: 'CHAPTER', number: '8', title: 'Infection prevention', children: [] },
      { id: 'c9', type: 'CHAPTER', number: '9', title: 'Medication administration', children: [] },
    ],
  },
];

// --- The section shown in the reader ------------------------------------------

export const SAMPLE_SECTION_BLOOD_PRESSURE: ContentDocument = {
  type: 'doc',
  content: [
    paragraph(
      'b-01',
      text('Blood pressure is the force exerted by circulating blood against the walls of the arteries. It is recorded as two values: the '),
      bold('systolic'),
      text(' pressure, when the ventricles contract, over the '),
      bold('diastolic'),
      text(' pressure, when the heart relaxes between beats.'),
    ),
    paragraph(
      'b-02',
      text('Because a single reading reflects a moment rather than a condition, a diagnosis of hypertension rests on repeated measurements taken correctly over time. The quality of the technique matters as much as the number it produces.'),
    ),
    callout(
      'b-03',
      'key-term',
      'Pulse pressure',
      'The difference between systolic and diastolic pressure. A resting pulse pressure of about 40 mmHg is typical in adults; a persistently wide pulse pressure can indicate reduced arterial compliance.',
    ),
    heading('b-04', 'Classifying adult readings'),
    paragraph(
      'b-05',
      text('Readings are classified using the higher category reached by either value. A reading of 128/84 mmHg is therefore Stage 1, not Elevated, because the diastolic value places it there.'),
    ),
    table(
      'b-06',
      'Blood pressure categories for adults (ACC/AHA, 2017)',
      ['Category', 'Systolic (mmHg)', 'Diastolic (mmHg)'],
      [
        ['Normal', 'Less than 120', 'and less than 80'],
        ['Elevated', '120–129', 'and less than 80'],
        ['Hypertension, stage 1', '130–139', 'or 80–89'],
        ['Hypertension, stage 2', '140 or higher', 'or 90 or higher'],
        ['Hypertensive crisis', 'Higher than 180', 'and/or higher than 120'],
      ],
    ),
    callout(
      'b-07',
      'clinical-alert',
      'Escalate immediately',
      'A reading above 180/120 mmHg with chest pain, shortness of breath, visual disturbance or new neurological signs is a hypertensive emergency. Do not wait to repeat the measurement before escalating care.',
    ),
    heading('b-08', 'Measuring accurately'),
    paragraph(
      'b-09',
      text('Most measurement error comes from preparation and positioning rather than from the device. Before recording a value, confirm each of the following:'),
    ),
    bulletList('b-10', [
      [text('The patient has rested, seated, for at least five minutes, with no caffeine, exercise or smoking in the previous 30 minutes.')],
      [text('The back is supported, feet are flat on the floor, and legs are uncrossed.')],
      [text('The upper arm is bare and supported at heart level.')],
      [bold('The cuff bladder encircles at least 80% of the arm. '), text('A cuff that is too small overestimates pressure.')],
    ]),
    {
      type: 'figure',
      attrs: {
        blockId: 'b-11',
        src: '/preview/bp-categories.svg',
        alt: 'Horizontal bands showing systolic pressure from 90 to 190 mmHg, divided into normal, elevated, stage 1, stage 2 and crisis ranges.',
        caption: 'Figure 6.4. Systolic ranges by category. Diastolic values can move a reading into a higher category.',
      },
    },
    callout(
      'b-12',
      'practice-point',
      'Document what you did, not only what you found',
      'Record the arm used, patient position, and cuff size alongside the reading. A later value can only be compared with this one if the conditions are known.',
    ),
  ],
};

// --- Search -------------------------------------------------------------------

export interface SampleSearchHit {
  readonly sectionId: string;
  readonly sectionNumber: string;
  readonly sectionTitle: string;
  readonly blockId: string;
  /** Snippet with the matched phrase wrapped in [[ ]] for highlighting. */
  readonly snippet: string;
}

export interface SampleSearchGroup {
  readonly chapterNumber: string;
  readonly chapterTitle: string;
  readonly hits: readonly SampleSearchHit[];
}

export const SAMPLE_SEARCH = {
  query: 'blood pressure',
  total: 6,
  groups: [
    {
      chapterNumber: '6',
      chapterTitle: 'Vital signs',
      hits: [
        {
          sectionId: 's64',
          sectionNumber: '6.4',
          sectionTitle: 'Blood pressure',
          blockId: 'b-01',
          snippet: '[[Blood pressure]] is the force exerted by circulating blood against the walls of the arteries.',
        },
        {
          sectionId: 's64',
          sectionNumber: '6.4',
          sectionTitle: 'Blood pressure',
          blockId: 'b-06',
          snippet: '[[Blood pressure]] categories for adults. Readings are classified using the higher category reached by either value.',
        },
        {
          sectionId: 's62',
          sectionNumber: '6.2',
          sectionTitle: 'Pulse',
          blockId: 'p-14',
          snippet: 'A weak, thready pulse alongside falling [[blood pressure]] is an early sign of hypovolaemic shock.',
        },
      ],
    },
    {
      chapterNumber: '7',
      chapterTitle: 'Physical examination',
      hits: [
        {
          sectionId: 's72',
          sectionNumber: '7.2',
          sectionTitle: 'Cardiovascular assessment',
          blockId: 'x-03',
          snippet: 'Compare [[blood pressure]] in both arms at the first assessment; a difference above 10 mmHg warrants review.',
        },
      ],
    },
    {
      chapterNumber: '9',
      chapterTitle: 'Medication administration',
      hits: [
        {
          sectionId: 's93',
          sectionNumber: '9.3',
          sectionTitle: 'Before administering',
          blockId: 'm-08',
          snippet: 'Check [[blood pressure]] before giving an antihypertensive and withhold it if the reading is below the prescribed threshold.',
        },
        {
          sectionId: 's95',
          sectionNumber: '9.5',
          sectionTitle: 'Monitoring after administration',
          blockId: 'm-21',
          snippet: 'Postural [[blood pressure]] drops are common after the first dose of several cardiovascular medicines.',
        },
      ],
    },
  ] satisfies readonly SampleSearchGroup[],
};

// --- CMS version history ----------------------------------------------------

export interface SampleVersion {
  readonly number: number;
  readonly author: string;
  readonly publishedOn: string;
  readonly note: string;
  readonly status: 'published' | 'superseded' | 'draft';
}

export const SAMPLE_VERSIONS: readonly SampleVersion[] = [
  { number: 8, author: 'Content editor A', publishedOn: 'Not published', note: 'Add documentation practice point', status: 'draft' },
  { number: 7, author: 'Content editor A', publishedOn: '9 September 2026, 14:20', note: 'Update categories to ACC/AHA 2017 thresholds', status: 'published' },
  { number: 6, author: 'Content editor B', publishedOn: '2 September 2026, 10:05', note: 'Correct cuff sizing guidance', status: 'superseded' },
  { number: 5, author: 'Content editor B', publishedOn: '28 August 2026, 16:42', note: 'Imported from Word source, reviewed', status: 'superseded' },
];
