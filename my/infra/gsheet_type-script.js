const _sheet = SpreadsheetApp.getActiveSpreadsheet();
const tc_sheet = _sheet.getSheetByName("typecasts");
const tr_sheet = _sheet.getSheetByName("transforms");

const idxs = tc_sheet.getSheetValues(3, 2, 42, 1).map(row => `${row[0]}`);

/**
 * Renders the impacts of a given transform on a per-type basis.
 *
 * @param {String[][]} sources List of idxs for the source of each transform.
 * @param {String[][]} targets List of idxs for the target of each transform.
 * @return {String[][]} range of '-' for sources, '+' for targets, and '-/+' for self-references.
 * @customfunction
 */
function TRANSFORM_RENDER(sources, targets) {
  const src = sources.flat();
  const tgt = targets.flat();
  //return src.map(s => tgt.map(t => `${s}-${t}`))
  return src.map((source, i) => apply_transform(`${source}`, `${tgt[i]}`));
}

const _DEFAULTS = [
  // All super->sub transformations are implicit
  RegExp("^{i0}-{i0}.*$"),
  // Scalar -> Scalar is handled by each type
  RegExp('^12\d*-12\d*.*$'),
  // str|byte -> str|byte is handled by internal machinery
  RegExp('^11[12]-11[12]$'),
  // Vec and Map types handle intra-family conversions
  RegExp('^21\d*-21\d*$'),
  RegExp('^22\d*-22\d*$'),
];

/**
 * Determine whether the given transformation is covered implicitly, aka done "by default".
 *
 * @param {String} idx0
 * @param {String} idx1
 */
function is_def(idx0, idx1) {
  return _DEFAULTS.some(rgx => rgx.exec(`${idx0}-${idx1}`));
}

/**
 * Constructs a matrix of transform results for the given transforms, describing which cases are
 * covered.
 *
 * @param {String[][]} typelist the list of all recorded type `(name, idxs)` pairs.
 * @param {String[][]} transforms '-' for sources, '+' for targets, and '-/+' for self-references.
 * @return {String[][]} cells containing numbers 0-9 (num of overlapping casts).
 * @customfunction
 */
function TYPECAST_RENDER(transforms) {
  // Create a flat list of all source-target pairs
  const flattened = transforms.flatMap((row, i) => {
    const _tt0 = row.filter(v => v.includes('-'));
    const _tt1 = row.filter(v => v.includes('+'));
    return _tt0.flatMap(_t0 => _tt1.map(_t1 => `${_t0}-${_t1}`));
  });

  // Generate one cell per type/type combo
  return idxs.map(idx0 => idxs.map(idx1 => {
    uid = `${idx0}-${idx1}`;
    n = flattened.filter(pair => pair === uid).length;
    if (n > 0) {
      // Tag already-covered cases
      return `${n}`;
    } else if (is_def(idx0, idx1)) {
      // Calculate defaults


    }


  }));
}

/**
 *
 * @param {String} source
 * @param {String} target
 * @return {String[]}
 * @customfunction
 */
function apply_transform(source, target) {
  const rgx0 = RegExp(`^${source}`);
  const rgx1 = RegExp(`^${target}`);

  return idxs.map(idx => {
    // Skip indices shorter than the target.
    if (idx.length < target.length || idx.length < source.length) {
      return '';
    }

    let is_from = idx.length >= source.length && rgx0.exec(idx);
    let is_to = idx.length >= target.length && rgx1.exec(idx);
    if (is_from && is_to) {
      return "+/-";
    } else if (is_from) {
      return "-";
    } else if (is_to) {
      return "+";
    } else {
      return "";
    }
  });
}

ret = apply_transform('a', 'b');
