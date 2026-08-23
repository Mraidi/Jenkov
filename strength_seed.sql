-- strength_seed.sql
-- Observed catalog: what I actually train today, not everything possible.
-- Equipment: adjustable dumbbells, pull-up bar, dip station, adjustable bench.
--
-- This list is deliberately small. New movements get added the first time I
-- say one, via the resolution flow — never created silently by the agent.
-- Run after strength_schema.sql.

-- ---------------------------------------------------------------------------
-- exercises
-- is_bodyweight_base = 1 means load_value on a set is ADDED weight, or null.
-- ---------------------------------------------------------------------------

INSERT INTO exercises (canonical_name, movement_pattern, primary_muscle, equipment, is_bodyweight_base) VALUES
-- push: chest
('incline dumbbell bench press',       'horizontal push', 'chest',     'dumbbell',   0),
('flat dumbbell bench press',          'horizontal push', 'chest',     'dumbbell',   0),
('decline dumbbell bench press',       'horizontal push', 'chest',     'dumbbell',   0),
('dumbbell fly',                       'horizontal push', 'chest',     'dumbbell',   0),
('incline dumbbell fly',               'horizontal push', 'chest',     'dumbbell',   0),
('dumbbell pullover',                  'vertical pull',   'chest',     'dumbbell',   0),
('parallel bar dip',                   'vertical push',   'chest',     'bodyweight', 1),
('push-up',                            'horizontal push', 'chest',     'bodyweight', 1),
('diamond push-up',                    'horizontal push', 'triceps',   'bodyweight', 1),
('wide push-up',                       'horizontal push', 'chest',     'bodyweight', 1),
('decline push-up',                    'horizontal push', 'chest',     'bodyweight', 1),
('archer push-up',                     'horizontal push', 'chest',     'bodyweight', 1),

-- push: shoulders
('dumbbell lateral raise',             'lateral raise',   'delts',     'dumbbell',   0),

-- pull: back
('pull-up',                            'vertical pull',   'lats',      'bodyweight', 1),
('chin-up',                            'vertical pull',   'lats',      'bodyweight', 1),
('neutral grip pull-up',               'vertical pull',   'lats',      'bodyweight', 1),
('wide grip pull-up',                  'vertical pull',   'lats',      'bodyweight', 1),
('single arm dumbbell row',            'horizontal pull', 'lats',      'dumbbell',   0),
('chest supported dumbbell row',       'horizontal pull', 'upper back','dumbbell',   0),
('bent over two arm dumbbell row',     'horizontal pull', 'lats',      'dumbbell',   0),
('bent over dumbbell reverse fly',     'horizontal pull', 'rear delts','dumbbell',   0),
('dumbbell shrug',                     'shrug',           'traps',     'dumbbell',   0),

-- legs
('goblet squat',                       'squat',           'quads',     'dumbbell',   0),
('dumbbell front squat',               'squat',           'quads',     'dumbbell',   0),
('bulgarian split squat',              'squat',           'quads',     'dumbbell',   0),
('dumbbell lunge',                     'lunge',           'quads',     'dumbbell',   0),
('dumbbell romanian deadlift',         'hinge',           'hamstrings','dumbbell',   0),
('dumbbell hip thrust',                'hinge',           'glutes',    'dumbbell',   0),
('standing dumbbell calf raise',       'calf raise',      'calves',    'dumbbell',   0),

-- biceps
('standing dumbbell curl',             'elbow flexion',   'biceps',    'dumbbell',   0),
('incline dumbbell curl',              'elbow flexion',   'biceps',    'dumbbell',   0),
('preacher curl',                      'elbow flexion',   'biceps',    'dumbbell',   0),
('dumbbell concentration curl',        'elbow flexion',   'biceps',    'dumbbell',   0),

-- triceps
('bench dip',                          'elbow extension', 'triceps',   'bodyweight', 1),
('dumbbell skull crusher',             'elbow extension', 'triceps',   'dumbbell',   0),
('seated dumbbell overhead triceps extension', 'elbow extension', 'triceps', 'dumbbell', 0),

-- core / neck
('captains chair leg raise',           'hip flexion',     'abs',       'bodyweight', 1),
('neck flexion',                       'neck',            'neck',      'bodyweight', 1),
('neck extension',                     'neck',            'neck',      'bodyweight', 1);

-- ---------------------------------------------------------------------------
-- exercise_aliases
-- Everything I plausibly say out loud mid-set. Stored lowercase.
-- The canonical name itself does not need an alias row — resolution checks
-- canonical_name first, then this table.
-- ---------------------------------------------------------------------------

INSERT INTO exercise_aliases (exercise_id, alias)
SELECT id, alias FROM exercises JOIN (
    SELECT 'incline dumbbell bench press' AS cn, 'incline press' AS alias UNION ALL
    SELECT 'incline dumbbell bench press', 'incline bench' UNION ALL
    SELECT 'incline dumbbell bench press', 'incline db press' UNION ALL
    SELECT 'incline dumbbell bench press', 'incline dumbbell press' UNION ALL

    SELECT 'flat dumbbell bench press', 'bench' UNION ALL
    SELECT 'flat dumbbell bench press', 'flat bench' UNION ALL
    SELECT 'flat dumbbell bench press', 'dumbbell bench' UNION ALL
    SELECT 'flat dumbbell bench press', 'db bench press' UNION ALL
    SELECT 'flat dumbbell bench press', 'dumbbell bench press' UNION ALL

    SELECT 'decline dumbbell bench press', 'decline bench' UNION ALL
    SELECT 'decline dumbbell bench press', 'decline press' UNION ALL

    SELECT 'dumbbell fly', 'flies' UNION ALL
    SELECT 'dumbbell fly', 'flyes' UNION ALL
    SELECT 'dumbbell fly', 'chest fly' UNION ALL
    SELECT 'incline dumbbell fly', 'incline fly' UNION ALL

    SELECT 'dumbbell pullover', 'pullover' UNION ALL
    SELECT 'dumbbell pullover', 'pullovers' UNION ALL

    SELECT 'parallel bar dip', 'dips' UNION ALL
    SELECT 'parallel bar dip', 'dip' UNION ALL
    SELECT 'parallel bar dip', 'chest dips' UNION ALL

    SELECT 'push-up', 'pushups' UNION ALL
    SELECT 'push-up', 'push ups' UNION ALL
    SELECT 'push-up', 'pushup' UNION ALL
    SELECT 'diamond push-up', 'diamond pushups' UNION ALL
    SELECT 'diamond push-up', 'close grip pushups' UNION ALL
    SELECT 'wide push-up', 'wide pushups' UNION ALL
    SELECT 'decline push-up', 'decline pushups' UNION ALL
    SELECT 'decline push-up', 'feet elevated pushups' UNION ALL
    SELECT 'archer push-up', 'archer pushups' UNION ALL

    SELECT 'dumbbell lateral raise', 'lateral raise' UNION ALL
    SELECT 'dumbbell lateral raise', 'lat raises' UNION ALL
    SELECT 'dumbbell lateral raise', 'side raises' UNION ALL

    SELECT 'pull-up', 'pullups' UNION ALL
    SELECT 'pull-up', 'pull ups' UNION ALL
    SELECT 'pull-up', 'pullup' UNION ALL
    SELECT 'chin-up', 'chinups' UNION ALL
    SELECT 'chin-up', 'chin ups' UNION ALL
    SELECT 'chin-up', 'supinated pullups' UNION ALL
    SELECT 'neutral grip pull-up', 'neutral pullups' UNION ALL
    SELECT 'neutral grip pull-up', 'hammer grip pullups' UNION ALL
    SELECT 'wide grip pull-up', 'wide pullups' UNION ALL

    SELECT 'single arm dumbbell row', 'one arm row' UNION ALL
    SELECT 'single arm dumbbell row', 'single arm row' UNION ALL
    SELECT 'single arm dumbbell row', 'dumbbell row' UNION ALL
    SELECT 'chest supported dumbbell row', 'chest supported row' UNION ALL
    SELECT 'chest supported dumbbell row', 'supported rows' UNION ALL
    SELECT 'bent over two arm dumbbell row', 'bent over row' UNION ALL
    SELECT 'bent over two arm dumbbell row', 'two arm row' UNION ALL
    SELECT 'bent over dumbbell reverse fly', 'reverse fly' UNION ALL
    SELECT 'bent over dumbbell reverse fly', 'rear delt fly' UNION ALL
    SELECT 'bent over dumbbell reverse fly', 'bent over fly' UNION ALL
    SELECT 'dumbbell shrug', 'shrugs' UNION ALL

    SELECT 'goblet squat', 'squats' UNION ALL
    SELECT 'goblet squat', 'goblet squats' UNION ALL
    SELECT 'dumbbell front squat', 'front squats' UNION ALL
    SELECT 'bulgarian split squat', 'bulgarians' UNION ALL
    SELECT 'bulgarian split squat', 'split squats' UNION ALL
    SELECT 'dumbbell lunge', 'lunges' UNION ALL
    SELECT 'dumbbell romanian deadlift', 'rdl' UNION ALL
    SELECT 'dumbbell romanian deadlift', 'rdls' UNION ALL
    SELECT 'dumbbell romanian deadlift', 'romanian deadlift' UNION ALL
    SELECT 'dumbbell hip thrust', 'hip thrusts' UNION ALL
    SELECT 'standing dumbbell calf raise', 'calf raises' UNION ALL
    SELECT 'standing dumbbell calf raise', 'calves' UNION ALL

    SELECT 'standing dumbbell curl', 'curls' UNION ALL
    SELECT 'standing dumbbell curl', 'bicep curls' UNION ALL
    SELECT 'standing dumbbell curl', 'standing curls' UNION ALL
    SELECT 'incline dumbbell curl', 'incline curls' UNION ALL
    SELECT 'preacher curl', 'preacher curls' UNION ALL
    SELECT 'dumbbell concentration curl', 'concentration curls' UNION ALL

    SELECT 'bench dip', 'bench dips' UNION ALL
    SELECT 'bench dip', 'tricep dips' UNION ALL
    SELECT 'dumbbell skull crusher', 'skull crushers' UNION ALL
    SELECT 'dumbbell skull crusher', 'skullcrushers' UNION ALL
    SELECT 'seated dumbbell overhead triceps extension', 'tricep extension' UNION ALL
    SELECT 'seated dumbbell overhead triceps extension', 'overhead extension' UNION ALL
    SELECT 'seated dumbbell overhead triceps extension', 'seated tricep extension' UNION ALL

    SELECT 'captains chair leg raise', 'leg raises' UNION ALL
    SELECT 'captains chair leg raise', 'hanging leg raises' UNION ALL
    SELECT 'captains chair leg raise', 'abs' UNION ALL
    SELECT 'neck flexion', 'neck curls' UNION ALL
    SELECT 'neck extension', 'neck extensions'
) a ON a.cn = exercises.canonical_name;
