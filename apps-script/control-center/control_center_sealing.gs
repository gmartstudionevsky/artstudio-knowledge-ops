/**
 * ARTSTUDIO Control Center Sealing Script.
 *
 * Stage 2 version: prepares canonical Drive structure, audits, executes safe
 * approved actions, and trashes obvious duplicates without permanent deletion.
 */

const CONFIG = {
  artstudioFolderId: '17dKXkxMd_iiBz5AFbKtt7YvuEzo-bfQK',
  controlCenterFolderId: '13riY7cN6DjiYg1k9ey19sdFgva8cP7dp',
  timezone: 'Europe/Moscow',
  maxScanDepth: 12,
  reorganizationPlanName: 'ARTSTUDIO_Reorganization_Plan',
  toolRunLogName: 'ARTSTUDIO_Tool_Run_Log',
  auditSheetName: 'Drive Audit Snapshot',
  duplicateReportSheetName: 'Duplicate Report',
  namingIssuesSheetName: 'Naming Issues',
  validationSheetName: 'Stage 2 Readiness Validation',
  allowPermanentDelete: false,
  allowTrashObviousDuplicates: true,
  autoSafeActionsEnabled: true,
  rootFolders: [
    '00_CONTROL_CENTER',
    '01_INBOX',
    '02_Brand_Context',
    '03_Object_Data',
    '04_Standards_SOP',
    '05_Official_Sites',
    '06_OTA',
    '07_Reviews',
    '08_Legal_Files',
    '09_Owner_Investor',
    '10_Competitors_Market'
  ],
  controlCenterSubfolders: [
    '98_Project_Methodology',
    '99_Setup_Archive'
  ],
  canonicalControlFiles: [
    'ARTSTUDIO_Master_Index',
    'ARTSTUDIO_Source_Map',
    'ARTSTUDIO_Decision_Log',
    'ARTSTUDIO_Open_Questions',
    'ARTSTUDIO_Project_Roadmap',
    'ARTSTUDIO_Reorganization_Plan',
    'ARTSTUDIO_Glossary',
    'ARTSTUDIO_Context_Request_Log',
    'ARTSTUDIO_Tool_Run_Log',
    'ARTSTUDIO_Codex_Handoff_Log',
    'ARTSTUDIO_Drive_Rules'
  ],
  setupArtifacts: [
    'ARTSTUDIO_CONTROL_CENTER_SPEC',
    'ARTSTUDIO_CONTROL_CENTER_SCRIPT_TASK',
    'ARTSTUDIO_CONTROL_CENTER_SEALING_TASK',
    'bootstrap_control_center.gs',
    'control_center_sealing.gs'
  ],
  methodologyPrefix: 'ARTSTUDIO Base'
};

const MAIN_HEADERS = [
  'Action ID', 'Current file / folder', 'Current location', 'Problem',
  'Recommended action', 'Target name', 'Target location', 'Priority', 'Risk',
  'Machine recommendation', 'Human decision', 'Execution status', 'Executed by',
  'Date', 'Object ID', 'Object URL', 'Object type', 'Canonical object ID',
  'Canonical object URL', 'Detection rule', 'Compare result',
  'Unique content risk', 'Safe action', 'Execution log', 'Last checked'
];

const AUDIT_HEADERS = [
  'Snapshot ID', 'Scan time', 'Object ID', 'Object name', 'Object type',
  'MIME type', 'URL', 'Parent ID', 'Parent name', 'Location type',
  'Created time', 'Modified time', 'Notes'
];

const FINDING_HEADERS = [
  'Snapshot ID', 'Detection time', 'Object ID', 'Object name', 'URL',
  'Location', 'Detection rule', 'Problem', 'Recommended action',
  'Safe action', 'Risk', 'Compare result', 'Status'
];

const VALIDATION_HEADERS = [
  'Check ID', 'Check name', 'Expected', 'Actual', 'Status', 'Notes', 'Checked at'
];

function getConfig() {
  return CONFIG;
}

function mainPrepareDriveStructure() {
  validateConfig_();
  const ctx = buildContext_();
  const created = [];

  CONFIG.rootFolders.forEach(function(name) {
    const folder = getOrCreateFolder(ctx.artstudioFolder, name);
    if (folder.created) created.push(name);
  });

  CONFIG.controlCenterSubfolders.forEach(function(name) {
    const folder = getOrCreateFolder(ctx.controlCenterFolder, name);
    if (folder.created) created.push('00_CONTROL_CENTER/' + name);
  });

  appendToolRunLog(ctx, {
    runId: runId_('PREP'),
    task: 'Prepare canonical Drive structure',
    output: created.length ? 'Created: ' + created.join(', ') : 'All canonical folders already exist',
    status: 'completed',
    reviewRequired: 'no',
    notes: 'No files were deleted or permission changes made.'
  });

  return { created: created };
}

function mainAuditOnly() {
  validateConfig_();
  const ctx = buildContext_();
  const snapshotId = runId_('AUDIT');
  const scanTime = now_();
  const records = dedupeRecords_(scanFolderRecursive_(ctx.artstudioFolder, 'ARTSTUDIO', 0));
  const canonical = findCanonicalControlFiles(records);
  const findings = buildFindings(records, canonical);

  writeDriveAuditSnapshot(ctx.reorganizationSpreadsheet, records, snapshotId, scanTime);
  writeFindings(ctx.reorganizationSpreadsheet, CONFIG.duplicateReportSheetName, findings.duplicates, snapshotId, scanTime);
  writeFindings(ctx.reorganizationSpreadsheet, CONFIG.namingIssuesSheetName, findings.naming, snapshotId, scanTime);
  writeReorganizationPlanRows(ctx.reorganizationSpreadsheet, findings.recommendations, scanTime);
  writeValidationReport(ctx.reorganizationSpreadsheet, records, findings, canonical);

  appendToolRunLog(ctx, {
    runId: snapshotId,
    task: 'Stage 2 audit-only scan',
    output: 'Scanned ' + records.length + ' objects; prepared ' + findings.recommendations.length + ' recommendations',
    status: 'completed',
    reviewRequired: findings.recommendations.length ? 'yes' : 'no',
    notes: 'Audit-only: no move, rename, trash or permission change executed.'
  });

  return { snapshotId: snapshotId, records: records.length, recommendations: findings.recommendations.length };
}

function mainExecuteSafeActions() {
  validateConfig_();
  const ctx = buildContext_();
  const sheet = ensureSheet_(ctx.reorganizationSpreadsheet, 'Main', MAIN_HEADERS);
  const headers = getHeaders_(sheet);
  const rows = sheet.getLastRow() > 1 ? sheet.getRange(2, 1, sheet.getLastRow() - 1, headers.length).getValues() : [];
  const results = [];

  rows.forEach(function(row, idx) {
    const rowNumber = idx + 2;
    const item = rowToObject_(headers, row);
    if (!shouldExecuteRow_(item)) return;
    const result = executePlanRow_(ctx, item);
    results.push(result);
    updateExecutionCells_(sheet, headers, rowNumber, result);
  });

  appendToolRunLog(ctx, {
    runId: runId_('EXEC'),
    task: 'Execute safe reorganization actions',
    output: 'Processed ' + results.length + ' executable rows',
    status: results.some(function(r) { return r.status === 'failed'; }) ? 'completed with errors' : 'completed',
    reviewRequired: results.some(function(r) { return r.status === 'blocked'; }) ? 'yes' : 'no',
    notes: 'Permanent delete is disabled; duplicate removal uses Drive trash only.'
  });

  return { processed: results.length, results: results };
}

function mainValidateStageTwoReadiness() {
  validateConfig_();
  const ctx = buildContext_();
  const records = dedupeRecords_(scanFolderRecursive_(ctx.artstudioFolder, 'ARTSTUDIO', 0));
  const canonical = findCanonicalControlFiles(records);
  const findings = buildFindings(records, canonical);
  writeValidationReport(ctx.reorganizationSpreadsheet, records, findings, canonical);
  appendToolRunLog(ctx, {
    runId: runId_('VAL'),
    task: 'Validate Stage 2 readiness',
    output: 'Validation report refreshed',
    status: 'completed',
    reviewRequired: findings.recommendations.length ? 'yes' : 'no',
    notes: 'Readiness validation only.'
  });
}

function getOrCreateFolder(parentFolder, folderName) {
  const folders = parentFolder.getFoldersByName(folderName);
  if (folders.hasNext()) return { folder: folders.next(), created: false };
  return { folder: parentFolder.createFolder(folderName), created: true };
}

function findCanonicalControlFiles(records) {
  const canonical = {};
  records.forEach(function(record) {
    if (record.parentId === CONFIG.controlCenterFolderId && CONFIG.canonicalControlFiles.indexOf(record.objectName) !== -1) {
      canonical[record.objectName] = record;
    }
  });
  return canonical;
}

function buildFindings(records, canonical) {
  const recommendations = [];
  const duplicates = [];
  const naming = [];

  records.forEach(function(record) {
    if (CONFIG.canonicalControlFiles.indexOf(record.objectName) !== -1 && record.parentId !== CONFIG.controlCenterFolderId) {
      const c = canonical[record.objectName] || null;
      const compare = c ? compareDuplicateObjects(record, c) : 'canonical missing';
      const isObvious = c && compare === 'no unique content detected';
      const finding = recommendation_(record, {
        problem: 'Control file duplicate outside 00_CONTROL_CENTER.',
        recommendedAction: isObvious ? 'trash duplicate' : 'human review duplicate',
        safeAction: isObvious ? 'trash duplicate' : 'no automated action',
        targetLocation: 'Drive trash',
        detectionRule: 'DUPLICATE_CANONICAL_CONTROL_FILE',
        priority: 'P1',
        risk: isObvious ? 'low' : 'high',
        compareResult: compare,
        uniqueContentRisk: isObvious ? 'none detected' : 'unknown',
        canonical: c
      });
      duplicates.push(finding);
      recommendations.push(finding);
    }

    if (CONFIG.setupArtifacts.indexOf(record.objectName) !== -1) {
      recommendations.push(recommendation_(record, {
        problem: 'Setup artifact should be archived after bootstrap.',
        recommendedAction: 'archive setup artifact',
        safeAction: 'archive setup artifact',
        targetLocation: '00_CONTROL_CENTER/99_Setup_Archive',
        detectionRule: 'SETUP_ARTIFACT',
        priority: 'P2',
        risk: 'low'
      }));
    }

    if (record.objectName.indexOf(CONFIG.methodologyPrefix) === 0) {
      recommendations.push(recommendation_(record, {
        problem: 'Methodology artifact should be grouped under control-center methodology.',
        recommendedAction: 'move methodology file',
        safeAction: 'move methodology file',
        targetLocation: '00_CONTROL_CENTER/98_Project_Methodology',
        detectionRule: 'METHODOLOGY_FILE',
        priority: 'P2',
        risk: 'low'
      }));
    }

    if (record.objectType === 'folder' && record.parentId === CONFIG.artstudioFolderId) {
      const target = suggestedFolderName_(record.objectName);
      if (target && target !== record.objectName) {
        const finding = recommendation_(record, {
          problem: 'Folder naming does not match canonical numbering.',
          recommendedAction: 'rename folder',
          safeAction: 'rename folder',
          targetName: target,
          targetLocation: 'ARTSTUDIO',
          detectionRule: 'ROOT_FOLDER_NAMING',
          priority: 'P1',
          risk: 'medium'
        });
        naming.push(finding);
        recommendations.push(finding);
      }
    }
  });

  return {
    duplicates: dedupeRecommendations_(duplicates),
    naming: dedupeRecommendations_(naming),
    recommendations: dedupeRecommendations_(recommendations)
  };
}

function compareDuplicateObjects(duplicateRecord, canonicalRecord) {
  if (!canonicalRecord) return 'canonical missing';
  if (duplicateRecord.objectId === canonicalRecord.objectId) return 'same object';
  if (duplicateRecord.mimeType !== canonicalRecord.mimeType) return 'different mime type';
  if (duplicateRecord.size && canonicalRecord.size && duplicateRecord.size === canonicalRecord.size && duplicateRecord.modifiedTime === canonicalRecord.modifiedTime) {
    return 'no unique content detected';
  }
  if (duplicateRecord.modifiedTime === canonicalRecord.modifiedTime) return 'no unique content detected';
  return 'unique content possible';
}

function recommendation_(record, opts) {
  return {
    object: record,
    canonical: opts.canonical || null,
    problem: opts.problem,
    recommendedAction: opts.recommendedAction,
    targetName: opts.targetName || record.objectName,
    targetLocation: opts.targetLocation || '',
    priority: opts.priority || 'P2',
    risk: opts.risk || 'medium',
    machineRecommendation: opts.machineRecommendation || opts.problem,
    detectionRule: opts.detectionRule,
    compareResult: opts.compareResult || 'not applicable',
    uniqueContentRisk: opts.uniqueContentRisk || 'low',
    safeAction: opts.safeAction || 'no automated action'
  };
}

function executePlanRow_(ctx, item) {
  try {
    const action = normalize_(item['Safe action'] || item['Recommended action']);
    if (action === 'create folder') return createFolderFromRow_(ctx, item);
    if (action === 'rename file' || action === 'rename folder') return renameObjectFromRow_(item);
    if (action === 'move file' || action === 'move folder' || action === 'move methodology file' || action === 'archive setup artifact') return moveObjectFromRow_(ctx, item);
    if (action === 'trash duplicate') return trashDuplicateFromRow_(item);
    return result_('blocked', 'No automated handler for action: ' + action);
  } catch (err) {
    return result_('failed', err.message);
  }
}

function createFolderFromRow_(ctx, item) {
  const targetName = item['Target name'];
  const targetLocation = item['Target location'] || 'ARTSTUDIO';
  if (!targetName) return result_('blocked', 'Target name is required for create folder.');
  const parent = resolveFolderPath_(ctx, targetLocation);
  const created = getOrCreateFolder(parent, targetName);
  return result_('completed', created.created ? 'Created folder: ' + targetName : 'Folder already exists: ' + targetName);
}

function renameObjectFromRow_(item) {
  const id = item['Object ID'];
  const type = normalize_(item['Object type']);
  const targetName = item['Target name'];
  if (!id || !targetName) return result_('blocked', 'Object ID and Target name are required for rename.');
  const object = type === 'folder' ? DriveApp.getFolderById(id) : DriveApp.getFileById(id);
  object.setName(targetName);
  return result_('completed', 'Renamed to: ' + targetName);
}

function moveObjectFromRow_(ctx, item) {
  const id = item['Object ID'];
  const type = normalize_(item['Object type']);
  const targetLocation = item['Target location'];
  if (!id || !targetLocation) return result_('blocked', 'Object ID and Target location are required for move.');
  const target = resolveFolderPath_(ctx, targetLocation);
  const object = type === 'folder' ? DriveApp.getFolderById(id) : DriveApp.getFileById(id);
  object.moveTo(target);
  return result_('completed', 'Moved to: ' + targetLocation);
}

function trashDuplicateFromRow_(item) {
  if (!CONFIG.allowTrashObviousDuplicates) return result_('blocked', 'Trashing duplicates is disabled.');
  if (CONFIG.allowPermanentDelete) throw new Error('Permanent delete must remain disabled.');
  const id = item['Object ID'];
  const type = normalize_(item['Object type']);
  const compareResult = normalize_(item['Compare result']);
  const uniqueRisk = normalize_(item['Unique content risk']);
  if (!id) return result_('blocked', 'Object ID is required for trash duplicate.');
  if (type === 'folder' && !isFolderEmpty_(DriveApp.getFolderById(id))) return result_('blocked', 'Folder is not empty; human review required.');
  if (compareResult !== 'no unique content detected' && uniqueRisk !== 'none detected' && normalize_(item['Human decision']) !== 'accepted') {
    return result_('blocked', 'Duplicate is not obvious; human review required.');
  }
  const object = type === 'folder' ? DriveApp.getFolderById(id) : DriveApp.getFileById(id);
  object.setTrashed(true);
  return result_('completed', 'Moved duplicate to Drive trash.');
}

function shouldExecuteRow_(item) {
  const status = normalize_(item['Execution status']);
  if (status === 'completed') return false;
  const decision = normalize_(item['Human decision']);
  const risk = normalize_(item['Risk']);
  const action = normalize_(item['Safe action'] || item['Recommended action']);
  if (decision === 'rejected' || decision === 'postponed' || decision === 'needs discussion') return false;
  if (risk === 'high' && decision !== 'accepted') return false;
  if (decision === 'accepted') return true;
  return CONFIG.autoSafeActionsEnabled && risk !== 'high' && isAutoSafeAction_(action);
}

function isAutoSafeAction_(action) {
  return ['create folder', 'move file', 'move folder', 'rename file', 'rename folder', 'archive setup artifact', 'move methodology file', 'trash duplicate'].indexOf(action) !== -1;
}

function resolveFolderPath_(ctx, path) {
  const normalized = String(path || 'ARTSTUDIO').replace(/^ARTSTUDIO\/?/, '').replace(/^00_CONTROL_CENTER\/?/, '00_CONTROL_CENTER/');
  if (!normalized || normalized === 'ARTSTUDIO') return ctx.artstudioFolder;
  let current = ctx.artstudioFolder;
  normalized.split('/').filter(Boolean).forEach(function(part) {
    if (part === '00_CONTROL_CENTER') current = ctx.controlCenterFolder;
    else current = getOrCreateFolder(current, part).folder;
  });
  return current;
}

function suggestedFolderName_(name) {
  const map = {
    '00_Legal_Files': '08_Legal_Files',
    'Стандарты': '04_Standards_SOP',
    '01_Brand_Context': '02_Brand_Context',
    '02_Official_Sites': '05_Official_Sites',
    '03_OTA': '06_OTA',
    '04_Reviews': '07_Reviews',
    '05_Investor': '09_Owner_Investor',
    '06_Competitors': '10_Competitors_Market'
  };
  return map[name] || null;
}

function scanFolderRecursive_(folder, locationType, depth) {
  const records = [describeObject_(folder, 'folder', locationType, null)];
  const files = folder.getFiles();
  while (files.hasNext()) records.push(describeObject_(files.next(), 'file', locationType, folder));
  if (depth >= CONFIG.maxScanDepth) return records;
  const folders = folder.getFolders();
  while (folders.hasNext()) {
    const nested = folders.next();
    const nestedLocation = nested.getId() === CONFIG.controlCenterFolderId ? '00_CONTROL_CENTER' : locationType + '/' + nested.getName();
    records.push.apply(records, scanFolderRecursive_(nested, nestedLocation, depth + 1));
  }
  return records;
}

function describeObject_(object, objectType, locationType, parentFolder) {
  const parent = parentInfo_(object, parentFolder);
  return {
    objectId: object.getId(),
    objectName: object.getName(),
    objectType: objectType,
    mimeType: objectType === 'file' ? object.getMimeType() : 'application/vnd.google-apps.folder',
    size: objectType === 'file' ? object.getSize() : '',
    url: object.getUrl(),
    parentId: parent.id,
    parentName: parent.name,
    currentLocation: parent.name || locationType,
    locationType: locationType,
    createdTime: date_(object.getDateCreated()),
    modifiedTime: object.getLastUpdated ? date_(object.getLastUpdated()) : '',
    notes: ''
  };
}

function parentInfo_(object, parentFolder) {
  if (parentFolder) return { id: parentFolder.getId(), name: parentFolder.getName() };
  const parents = object.getParents();
  if (parents.hasNext()) {
    const parent = parents.next();
    return { id: parent.getId(), name: parent.getName() };
  }
  return { id: '', name: '' };
}

function writeDriveAuditSnapshot(spreadsheet, records, snapshotId, scanTime) {
  const sheet = resetSheet_(spreadsheet, CONFIG.auditSheetName, AUDIT_HEADERS);
  writeRows_(sheet, records.map(function(r) {
    return [snapshotId, scanTime, r.objectId, r.objectName, r.objectType, r.mimeType, r.url, r.parentId, r.parentName, r.locationType, r.createdTime, r.modifiedTime, r.notes];
  }));
}

function writeFindings(spreadsheet, sheetName, findings, snapshotId, scanTime) {
  const sheet = resetSheet_(spreadsheet, sheetName, FINDING_HEADERS);
  writeRows_(sheet, findings.map(function(f) {
    return [snapshotId, scanTime, f.object.objectId, f.object.objectName, f.object.url, f.object.currentLocation, f.detectionRule, f.problem, f.recommendedAction, f.safeAction, f.risk, f.compareResult, 'open'];
  }));
}

function writeReorganizationPlanRows(spreadsheet, recommendations, scanTime) {
  const sheet = ensureSheet_(spreadsheet, 'Main', MAIN_HEADERS);
  const headers = getHeaders_(sheet);
  const existing = existingKeys_(sheet, headers);
  const rows = [];
  recommendations.forEach(function(item) {
    const key = item.object.objectId + '|' + item.detectionRule;
    if (existing[key]) return;
    rows.push(rowFromMap_(headers, {
      'Action ID': 'ST2-' + item.detectionRule + '-' + String(item.object.objectId).slice(0, 8),
      'Current file / folder': item.object.objectName,
      'Current location': item.object.currentLocation,
      'Problem': item.problem,
      'Recommended action': item.recommendedAction,
      'Target name': item.targetName,
      'Target location': item.targetLocation,
      'Priority': item.priority,
      'Risk': item.risk,
      'Machine recommendation': item.machineRecommendation,
      'Human decision': item.risk === 'low' && item.safeAction !== 'no automated action' ? 'auto-safe' : '',
      'Execution status': 'not started',
      'Date': scanTime,
      'Object ID': item.object.objectId,
      'Object URL': item.object.url,
      'Object type': item.object.objectType,
      'Canonical object ID': item.canonical ? item.canonical.objectId : '',
      'Canonical object URL': item.canonical ? item.canonical.url : '',
      'Detection rule': item.detectionRule,
      'Compare result': item.compareResult,
      'Unique content risk': item.uniqueContentRisk,
      'Safe action': item.safeAction,
      'Execution log': 'Prepared by audit; not executed yet.',
      'Last checked': scanTime
    }));
    existing[key] = true;
  });
  writeRows_(sheet, rows);
}

function writeValidationReport(spreadsheet, records, findings, canonical) {
  const sheet = resetSheet_(spreadsheet, CONFIG.validationSheetName, VALIDATION_HEADERS);
  const checkedAt = now_();
  const rootNames = records.filter(function(r) { return r.parentId === CONFIG.artstudioFolderId && r.objectType === 'folder'; }).map(function(r) { return r.objectName; });
  const missing = CONFIG.rootFolders.filter(function(name) { return rootNames.indexOf(name) === -1 && name !== '00_CONTROL_CENTER'; });
  const canonicalCount = Object.keys(canonical).length;
  writeRows_(sheet, [
    ['ST2-VAL-001', 'Canonical root folders', 'all configured folders exist', missing.length ? missing.join(', ') : 'all present', missing.length ? 'WARN' : 'PASS', '', checkedAt],
    ['ST2-VAL-002', 'Control center files', '11 canonical files', String(canonicalCount), canonicalCount === 11 ? 'PASS' : 'WARN', '', checkedAt],
    ['ST2-VAL-003', 'Duplicate findings', '0 preferred after execution', String(findings.duplicates.length), findings.duplicates.length ? 'WARN' : 'PASS', '', checkedAt],
    ['ST2-VAL-004', 'Naming findings', '0 preferred after execution', String(findings.naming.length), findings.naming.length ? 'WARN' : 'PASS', '', checkedAt],
    ['ST2-VAL-005', 'Trash policy', 'permanent delete disabled', 'allowPermanentDelete=' + CONFIG.allowPermanentDelete, CONFIG.allowPermanentDelete ? 'FAIL' : 'PASS', 'Duplicates use Drive trash only.', checkedAt]
  ]);
}

function appendToolRunLog(ctx, summary) {
  try {
    const spreadsheet = findSpreadsheetByName_(ctx.controlCenterFolder, CONFIG.toolRunLogName);
    const sheet = ensureSheet_(spreadsheet, CONFIG.toolRunLogName, [
      'Run ID', 'Date / time', 'Tool', 'Task', 'Input sources', 'Output',
      'Affected files', 'Status', 'Human review required', 'Human decision', 'Notes'
    ]);
    sheet.appendRow([
      summary.runId,
      now_(),
      'Google Apps Script',
      summary.task,
      'ARTSTUDIO Drive; 00_CONTROL_CENTER; GitHub policy config',
      summary.output,
      CONFIG.reorganizationPlanName,
      summary.status,
      summary.reviewRequired,
      '',
      summary.notes || ''
    ]);
  } catch (err) {
    Logger.log('Tool Run Log update skipped: ' + err.message);
  }
}

function buildContext_() {
  const artstudioFolder = DriveApp.getFolderById(CONFIG.artstudioFolderId);
  const controlCenterFolder = DriveApp.getFolderById(CONFIG.controlCenterFolderId);
  return {
    artstudioFolder: artstudioFolder,
    controlCenterFolder: controlCenterFolder,
    reorganizationSpreadsheet: findSpreadsheetByName_(controlCenterFolder, CONFIG.reorganizationPlanName)
  };
}

function validateConfig_() {
  if (!CONFIG.artstudioFolderId || !CONFIG.controlCenterFolderId) throw new Error('Folder IDs are required.');
  if (CONFIG.allowPermanentDelete) throw new Error('Permanent delete must remain disabled.');
  if (CONFIG.canonicalControlFiles.length !== 11) throw new Error('Expected 11 control files.');
}

function findSpreadsheetByName_(folder, name) {
  const files = folder.getFilesByName(name);
  while (files.hasNext()) {
    const file = files.next();
    if (file.getMimeType() === MimeType.GOOGLE_SHEETS) return SpreadsheetApp.openById(file.getId());
  }
  throw new Error('Spreadsheet not found: ' + name);
}

function ensureSheet_(spreadsheet, sheetName, headers) {
  let sheet = spreadsheet.getSheetByName(sheetName) || spreadsheet.insertSheet(sheetName);
  const current = getHeaders_(sheet);
  if (!current.length) sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  else headers.forEach(function(h) { if (current.indexOf(h) === -1) sheet.getRange(1, sheet.getLastColumn() + 1).setValue(h); });
  sheet.setFrozenRows(1);
  return sheet;
}

function resetSheet_(spreadsheet, sheetName, headers) {
  const sheet = spreadsheet.getSheetByName(sheetName) || spreadsheet.insertSheet(sheetName);
  sheet.clear();
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  sheet.setFrozenRows(1);
  return sheet;
}

function getHeaders_(sheet) {
  if (sheet.getLastRow() < 1 || sheet.getLastColumn() < 1) return [];
  return sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0].map(function(v) { return String(v || '').trim(); });
}

function writeRows_(sheet, rows) {
  if (!rows.length) return;
  sheet.getRange(sheet.getLastRow() + 1, 1, rows.length, rows[0].length).setValues(rows);
}

function existingKeys_(sheet, headers) {
  const keys = {};
  const objectIdx = headers.indexOf('Object ID');
  const ruleIdx = headers.indexOf('Detection rule');
  if (objectIdx === -1 || ruleIdx === -1 || sheet.getLastRow() < 2) return keys;
  sheet.getRange(2, 1, sheet.getLastRow() - 1, headers.length).getValues().forEach(function(row) {
    if (row[objectIdx] && row[ruleIdx]) keys[row[objectIdx] + '|' + row[ruleIdx]] = true;
  });
  return keys;
}

function rowToObject_(headers, row) {
  const out = {};
  headers.forEach(function(h, i) { out[h] = row[i]; });
  return out;
}

function rowFromMap_(headers, map) {
  return headers.map(function(h) { return Object.prototype.hasOwnProperty.call(map, h) ? map[h] : ''; });
}

function updateExecutionCells_(sheet, headers, rowNumber, result) {
  setCell_(sheet, headers, rowNumber, 'Execution status', result.status);
  setCell_(sheet, headers, rowNumber, 'Execution log', result.message);
  setCell_(sheet, headers, rowNumber, 'Executed by', 'Google Apps Script');
  setCell_(sheet, headers, rowNumber, 'Last checked', now_());
}

function setCell_(sheet, headers, rowNumber, header, value) {
  const idx = headers.indexOf(header);
  if (idx !== -1) sheet.getRange(rowNumber, idx + 1).setValue(value);
}

function isFolderEmpty_(folder) {
  return !folder.getFiles().hasNext() && !folder.getFolders().hasNext();
}

function dedupeRecords_(records) {
  const seen = {};
  return records.filter(function(r) {
    const key = r.objectId + '|' + r.parentId + '|' + r.locationType;
    if (seen[key]) return false;
    seen[key] = true;
    return true;
  });
}

function dedupeRecommendations_(items) {
  const seen = {};
  return items.filter(function(item) {
    const key = item.object.objectId + '|' + item.detectionRule;
    if (seen[key]) return false;
    seen[key] = true;
    return true;
  });
}

function result_(status, message) {
  return { status: status, message: message };
}

function normalize_(value) {
  return String(value || '').trim().toLowerCase();
}

function runId_(prefix) {
  return prefix + '-' + Utilities.formatDate(new Date(), CONFIG.timezone, 'yyyyMMdd-HHmmss');
}

function now_() {
  return Utilities.formatDate(new Date(), CONFIG.timezone, "yyyy-MM-dd'T'HH:mm:ss");
}

function date_(date) {
  return date ? Utilities.formatDate(date, CONFIG.timezone, "yyyy-MM-dd'T'HH:mm:ss") : '';
}
