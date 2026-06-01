/**
 * ARTSTUDIO Control Center Sealing Script.
 *
 * Stage 1 production version: safe audit-only scan and reporting.
 * It never deletes, moves, renames, or changes permissions from mainAuditOnly().
 */

const CONFIG = {
  artstudioFolderId: '17dKXkxMd_iiBz5AFbKtt7YvuEzo-bfQK',
  controlCenterFolderId: '13riY7cN6DjiYg1k9ey19sdFgva8cP7dp',
  controlCenterFolderName: '00_CONTROL_CENTER',
  rootScanEnabled: true,
  dryRun: true,
  executeAcceptedActions: false,
  allowDelete: false,
  setupArchiveFolderName: '99_Setup_Archive',
  methodologyFolderName: '98_Project_Methodology',
  reorganizationPlanName: 'ARTSTUDIO_Reorganization_Plan',
  toolRunLogName: 'ARTSTUDIO_Tool_Run_Log',
  auditSheetName: 'Drive Audit Snapshot',
  namingIssuesSheetName: 'Naming Issues',
  duplicateReportSheetName: 'Duplicate Report',
  validationSheetName: 'Stage 1 Sealing Validation',
  timezone: 'Europe/Moscow',
  maxScanDepth: 12,
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
  methodologyPrefix: 'ARTSTUDIO Base —'
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
  'Is inside ARTSTUDIO', 'Is inside 00_CONTROL_CENTER',
  'Is root-level project file', 'Created time', 'Modified time', 'Notes'
];

const DUPLICATE_HEADERS = [
  'Snapshot ID', 'Detection time', 'Duplicate object ID', 'Duplicate object name',
  'Duplicate URL', 'Duplicate location', 'Canonical object ID',
  'Canonical object URL', 'Compare result', 'Unique content risk',
  'Recommended action', 'Safe action', 'Status'
];

const NAMING_HEADERS = [
  'Snapshot ID', 'Detection time', 'Object ID', 'Object name', 'Object type',
  'URL', 'Current location', 'Detection rule', 'Problem', 'Suggested name',
  'Machine recommendation', 'Human decision', 'Status', 'Last checked'
];

const VALIDATION_HEADERS = [
  'Check ID', 'Check name', 'Expected', 'Actual', 'Status', 'Notes', 'Checked at'
];

function getConfig() {
  return CONFIG;
}

function mainAuditOnly() {
  ccSealValidateConfig_();

  const startedAt = ccSealNow_();
  const context = ccSealBuildContext_();
  const snapshotId = 'SEAL-' + Utilities.formatDate(new Date(), CONFIG.timezone, 'yyyyMMdd-HHmmss');

  const auditRecords = ccSealDedupeRecords_([]
    .concat(scanArtstudioFolder(context))
    .concat(scanControlCenterFolder(context))
    .concat(scanRootProjectFiles(context)));
  const canonicalFiles = findControlCenterFiles(context, auditRecords);
  const duplicateFindings = detectDuplicateControlFiles(auditRecords, canonicalFiles);
  const setupFindings = detectSetupArtifacts(auditRecords);
  const methodologyFindings = detectMethodologyFiles(auditRecords);
  const namingFindings = detectNamingIssues(auditRecords);
  const recommendations = ccSealBuildRecommendations_(
    duplicateFindings,
    setupFindings,
    methodologyFindings,
    namingFindings
  );

  writeDriveAuditSnapshot(context.reorganizationSpreadsheet, auditRecords, snapshotId, startedAt);
  writeDuplicateReport(context.reorganizationSpreadsheet, duplicateFindings, snapshotId, startedAt);
  writeNamingIssues(context.reorganizationSpreadsheet, namingFindings, snapshotId, startedAt);
  writeReorganizationPlanRows(context.reorganizationSpreadsheet, recommendations, startedAt);
  writeValidationReport(context.reorganizationSpreadsheet, {
    auditRecords: auditRecords,
    canonicalFiles: canonicalFiles,
    duplicateFindings: duplicateFindings,
    setupFindings: setupFindings,
    methodologyFindings: methodologyFindings,
    namingFindings: namingFindings,
    recommendations: recommendations
  });
  appendToolRunLog(context, {
    runId: snapshotId,
    startedAt: startedAt,
    recordsScanned: auditRecords.length,
    recommendations: recommendations.length,
    duplicates: duplicateFindings.length,
    namingIssues: namingFindings.length
  });

  Logger.log('Audit-only sealing completed: ' + snapshotId);
  return {
    snapshotId: snapshotId,
    recordsScanned: auditRecords.length,
    recommendations: recommendations.length,
    duplicates: duplicateFindings.length,
    namingIssues: namingFindings.length
  };
}

function mainExecuteAcceptedActions() {
  if (!CONFIG.executeAcceptedActions) {
    throw new Error('Execution is disabled. This production version supports audit-only sealing.');
  }
  throw new Error('Execution is intentionally not implemented in the Stage 1 audit-only release.');
}

function mainValidateStageOneClosure() {
  ccSealValidateConfig_();
  const context = ccSealBuildContext_();
  const auditRecords = ccSealDedupeRecords_([]
    .concat(scanArtstudioFolder(context))
    .concat(scanControlCenterFolder(context))
    .concat(scanRootProjectFiles(context)));
  const canonicalFiles = findControlCenterFiles(context, auditRecords);
  const duplicateFindings = detectDuplicateControlFiles(auditRecords, canonicalFiles);
  const setupFindings = detectSetupArtifacts(auditRecords);
  const methodologyFindings = detectMethodologyFiles(auditRecords);
  const namingFindings = detectNamingIssues(auditRecords);

  writeValidationReport(context.reorganizationSpreadsheet, {
    auditRecords: auditRecords,
    canonicalFiles: canonicalFiles,
    duplicateFindings: duplicateFindings,
    setupFindings: setupFindings,
    methodologyFindings: methodologyFindings,
    namingFindings: namingFindings,
    recommendations: []
  });

  appendToolRunLog(context, {
    runId: 'VAL-' + Utilities.formatDate(new Date(), CONFIG.timezone, 'yyyyMMdd-HHmmss'),
    startedAt: ccSealNow_(),
    recordsScanned: auditRecords.length,
    recommendations: 0,
    duplicates: duplicateFindings.length,
    namingIssues: namingFindings.length,
    validationOnly: true
  });
}

function scanArtstudioFolder(context) {
  return ccSealScanFolderRecursive_(context.artstudioFolder, 'ARTSTUDIO', 0, true);
}

function scanControlCenterFolder(context) {
  return ccSealScanFolderRecursive_(context.controlCenterFolder, '00_CONTROL_CENTER', 0, true);
}

function scanRootProjectFiles(context) {
  if (!CONFIG.rootScanEnabled || !context.artstudioParentFolder) {
    return [];
  }
  const records = [];
  const files = context.artstudioParentFolder.getFiles();
  while (files.hasNext()) {
    const file = files.next();
    if (ccSealIsProjectObjectName_(file.getName())) {
      const record = ccSealDescribeObject_(file, 'file', 'ROOT_PROJECT', context.artstudioParentFolder);
      record.isRootLevelProjectFile = true;
      records.push(record);
    }
  }
  const folders = context.artstudioParentFolder.getFolders();
  while (folders.hasNext()) {
    const folder = folders.next();
    if (folder.getId() !== CONFIG.artstudioFolderId && ccSealIsProjectObjectName_(folder.getName())) {
      const record = ccSealDescribeObject_(folder, 'folder', 'ROOT_PROJECT', context.artstudioParentFolder);
      record.isRootLevelProjectFile = true;
      records.push(record);
    }
  }
  return records;
}

function findControlCenterFiles(context, auditRecords) {
  const byName = {};
  const records = auditRecords || scanControlCenterFolder(context);
  records.forEach(function(record) {
    if (record.isInsideControlCenter && CONFIG.canonicalControlFiles.indexOf(record.objectName) !== -1) {
      byName[record.objectName] = record;
    }
  });
  return byName;
}

function detectDuplicateControlFiles(auditRecords, canonicalFiles) {
  const findings = [];
  auditRecords.forEach(function(record) {
    if (record.isInsideControlCenter || CONFIG.canonicalControlFiles.indexOf(record.objectName) === -1) {
      return;
    }
    const canonical = canonicalFiles[record.objectName] || null;
    findings.push({
      object: record,
      canonical: canonical,
      detectionRule: 'DUPLICATE_CANONICAL_CONTROL_FILE',
      problem: 'Canonical control file exists outside 00_CONTROL_CENTER.',
      recommendedAction: 'human review duplicate',
      machineRecommendation: 'Compare with the canonical control-center object before any archive or merge action.',
      safeAction: 'audit only; no move or delete',
      priority: 'P1',
      risk: canonical ? 'high' : 'medium',
      compareResult: canonical ? compareDuplicateObjects(record, canonical) : 'canonical missing in control center',
      uniqueContentRisk: 'unknown until human review'
    });
  });
  return findings;
}

function detectSetupArtifacts(auditRecords) {
  const setupNames = CONFIG.setupArtifacts.map(function(name) { return name.toLowerCase(); });
  return auditRecords.filter(function(record) {
    return setupNames.indexOf(record.objectName.toLowerCase()) !== -1;
  }).map(function(record) {
    return {
      object: record,
      detectionRule: 'SETUP_ARTIFACT',
      problem: 'Setup artifact remains visible after control-center bootstrap.',
      recommendedAction: 'archive setup artifact',
      targetName: record.objectName,
      targetLocation: CONFIG.controlCenterFolderName + '/' + CONFIG.setupArchiveFolderName,
      machineRecommendation: 'Archive after human review; keep for traceability, do not delete.',
      safeAction: 'archive after accepted decision',
      priority: 'P2',
      risk: 'low',
      compareResult: 'not applicable',
      uniqueContentRisk: 'low'
    };
  });
}

function detectMethodologyFiles(auditRecords) {
  return auditRecords.filter(function(record) {
    return record.objectName.indexOf(CONFIG.methodologyPrefix) === 0 ||
      record.objectName.indexOf('ARTSTUDIO Base вЂ”') === 0;
  }).map(function(record) {
    return {
      object: record,
      detectionRule: 'METHODOLOGY_FILE',
      problem: 'Methodology file should be grouped under the methodology area.',
      recommendedAction: 'move methodology file',
      targetName: record.objectName,
      targetLocation: CONFIG.controlCenterFolderName + '/' + CONFIG.methodologyFolderName,
      machineRecommendation: 'Move to methodology folder after human review.',
      safeAction: 'move after accepted decision',
      priority: 'P2',
      risk: 'medium',
      compareResult: 'not applicable',
      uniqueContentRisk: 'medium'
    };
  });
}

function detectNamingIssues(auditRecords) {
  const findings = [];
  auditRecords.forEach(function(record) {
    if (record.objectType !== 'folder' || record.parentId !== CONFIG.artstudioFolderId) {
      ccSealDetectEbookIssue_(record, findings);
      return;
    }

    if (/^00_/i.test(record.objectName) && record.objectName !== CONFIG.controlCenterFolderName) {
      findings.push(ccSealNamingFinding_(record, 'DUPLICATE_00_PREFIX',
        'Only 00_CONTROL_CENTER should use the 00 prefix at ARTSTUDIO root.',
        ccSealSuggestedName_(record.objectName),
        'Rename or move the folder after human approval.'));
    }

    if (!/^\d{2}_/.test(record.objectName) && ccSealLooksLikeSystemFolder_(record.objectName)) {
      findings.push(ccSealNamingFinding_(record, 'UNNUMBERED_SYSTEM_FOLDER',
        'System-level folder does not have a numeric prefix.',
        ccSealSuggestedName_(record.objectName),
        'Assign a stable NN_English_Name prefix after human approval.'));
    }

    if (ccSealHasCyrillic_(record.objectName) && ccSealHasLatin_(record.objectName)) {
      findings.push(ccSealNamingFinding_(record, 'MIXED_LANGUAGE_SYSTEM_NAME',
        'System folder mixes Cyrillic and Latin naming at the root level.',
        ccSealSuggestedName_(record.objectName),
        'Use a stable English technical folder name and document Russian wording inside.'));
    }

    ccSealDetectEbookIssue_(record, findings);
  });
  return ccSealDedupeFindings_(findings);
}

function compareDuplicateObjects(duplicateRecord, canonicalRecord) {
  if (!canonicalRecord) {
    return 'canonical missing';
  }
  if (duplicateRecord.objectId === canonicalRecord.objectId) {
    return 'same object';
  }
  if (duplicateRecord.mimeType !== canonicalRecord.mimeType) {
    return 'different mime type';
  }
  if (duplicateRecord.modifiedTime === canonicalRecord.modifiedTime) {
    return 'same modified timestamp';
  }
  return 'same name; content comparison required';
}

function writeDriveAuditSnapshot(spreadsheet, auditRecords, snapshotId, scanTime) {
  const sheet = ccSealResetSheet_(spreadsheet, CONFIG.auditSheetName, AUDIT_HEADERS);
  const rows = auditRecords.map(function(record) {
    return [
      snapshotId, scanTime, record.objectId, record.objectName, record.objectType,
      record.mimeType, record.url, record.parentId, record.parentName, record.locationType,
      ccSealBool_(record.isInsideArtstudio), ccSealBool_(record.isInsideControlCenter),
      ccSealBool_(record.isRootLevelProjectFile), record.createdTime, record.modifiedTime,
      record.notes || ''
    ];
  });
  ccSealWriteRows_(sheet, rows);
}

function writeDuplicateReport(spreadsheet, duplicateFindings, snapshotId, scanTime) {
  const sheet = ccSealResetSheet_(spreadsheet, CONFIG.duplicateReportSheetName, DUPLICATE_HEADERS);
  const rows = duplicateFindings.map(function(finding) {
    return [
      snapshotId, scanTime, finding.object.objectId, finding.object.objectName,
      finding.object.url, finding.object.currentLocation,
      finding.canonical ? finding.canonical.objectId : '',
      finding.canonical ? finding.canonical.url : '',
      finding.compareResult, finding.uniqueContentRisk, finding.recommendedAction,
      finding.safeAction, 'open'
    ];
  });
  ccSealWriteRows_(sheet, rows);
}

function writeNamingIssues(spreadsheet, namingFindings, snapshotId, scanTime) {
  const priorDecisions = ccSealReadDecisionMap_(spreadsheet, CONFIG.namingIssuesSheetName);
  const sheet = ccSealResetSheet_(spreadsheet, CONFIG.namingIssuesSheetName, NAMING_HEADERS);
  const rows = namingFindings.map(function(finding) {
    const key = ccSealKey_(finding.object.objectId, finding.detectionRule);
    return [
      snapshotId, scanTime, finding.object.objectId, finding.object.objectName,
      finding.object.objectType, finding.object.url, finding.object.currentLocation,
      finding.detectionRule, finding.problem, finding.targetName || '',
      finding.machineRecommendation, priorDecisions[key] || '', 'open', scanTime
    ];
  });
  ccSealWriteRows_(sheet, rows);
}

function writeReorganizationPlanRows(spreadsheet, recommendations, scanTime) {
  const sheet = ccSealEnsureSheet_(spreadsheet, 'Main', MAIN_HEADERS);
  const headers = ccSealGetHeaders_(sheet);
  const existingKeys = ccSealReadExistingRecommendationKeys_(sheet, headers);
  const rows = [];

  recommendations.forEach(function(item) {
    const key = ccSealKey_(item.object.objectId, item.detectionRule);
    if (existingKeys[key]) {
      return;
    }
    rows.push(ccSealRowFromMap_(headers, {
      'Action ID': ccSealActionId_(item.detectionRule, item.object.objectId),
      'Current file / folder': item.object.objectName,
      'Current location': item.object.currentLocation,
      'Problem': item.problem,
      'Recommended action': item.recommendedAction,
      'Target name': item.targetName || item.object.objectName,
      'Target location': item.targetLocation || '',
      'Priority': item.priority,
      'Risk': item.risk,
      'Machine recommendation': item.machineRecommendation,
      'Human decision': '',
      'Execution status': 'not started',
      'Executed by': '',
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
      'Execution log': 'Audit-only recommendation; no action executed.',
      'Last checked': scanTime
    }));
    existingKeys[key] = true;
  });

  ccSealWriteRows_(sheet, rows);
}

function writeValidationReport(spreadsheet, state) {
  const sheet = ccSealResetSheet_(spreadsheet, CONFIG.validationSheetName, VALIDATION_HEADERS);
  const checkedAt = ccSealNow_();
  const canonicalFound = Object.keys(state.canonicalFiles || {}).length;
  const rows = [
    ccSealValidationRow_('VAL-001', 'Control center folder configured', CONFIG.controlCenterFolderId, CONFIG.controlCenterFolderId, 'PASS', '', checkedAt),
    ccSealValidationRow_('VAL-002', 'Canonical files found in 00_CONTROL_CENTER', '11', String(canonicalFound), canonicalFound === 11 ? 'PASS' : 'WARN', 'Missing files require human review before closure.', checkedAt),
    ccSealValidationRow_('VAL-003', 'Duplicate canonical files reported', '0 preferred after execution', String(state.duplicateFindings.length), state.duplicateFindings.length ? 'WARN' : 'PASS', 'Audit-only can only report duplicates.', checkedAt),
    ccSealValidationRow_('VAL-004', 'Setup artifacts reported', '0 preferred after execution', String(state.setupFindings.length), state.setupFindings.length ? 'WARN' : 'PASS', 'Archive only after accepted human decision.', checkedAt),
    ccSealValidationRow_('VAL-005', 'Methodology files reported', '0 preferred outside methodology folder', String(state.methodologyFindings.length), state.methodologyFindings.length ? 'WARN' : 'PASS', 'Move only after accepted human decision.', checkedAt),
    ccSealValidationRow_('VAL-006', 'Naming issues reported', '0 preferred', String(state.namingFindings.length), state.namingFindings.length ? 'WARN' : 'PASS', 'Human decisions are required for naming changes.', checkedAt),
    ccSealValidationRow_('VAL-007', 'Audit-only safety mode', 'dryRun=true; executeAcceptedActions=false; allowDelete=false', 'dryRun=' + CONFIG.dryRun + '; executeAcceptedActions=' + CONFIG.executeAcceptedActions + '; allowDelete=' + CONFIG.allowDelete, ccSealIsSafeMode_() ? 'PASS' : 'FAIL', '', checkedAt),
    ccSealValidationRow_('VAL-008', 'Reorganization recommendations prepared', 'Rows added only for new Object ID + Detection rule', String(state.recommendations.length), 'PASS', 'Existing rows are preserved.', checkedAt)
  ];
  ccSealWriteRows_(sheet, rows);
}

function appendToolRunLog(context, summary) {
  try {
    const spreadsheet = ccSealFindSpreadsheetByName_(context.controlCenterFolder, CONFIG.toolRunLogName);
    const sheet = ccSealEnsureSheet_(spreadsheet, CONFIG.toolRunLogName, [
      'Run ID', 'Date / time', 'Tool', 'Task', 'Input sources', 'Output',
      'Affected files', 'Status', 'Human review required', 'Human decision', 'Notes'
    ]);
    sheet.appendRow([
      summary.runId,
      summary.startedAt,
      'Google Apps Script',
      summary.validationOnly ? 'Stage 1 sealing validation' : 'Stage 1 sealing audit-only scan',
      'ARTSTUDIO folder; 00_CONTROL_CENTER folder; root project files',
      'Scanned ' + summary.recordsScanned + ' objects; prepared ' + summary.recommendations + ' recommendations',
      CONFIG.reorganizationPlanName,
      'completed',
      summary.recommendations || summary.duplicates || summary.namingIssues ? 'yes' : 'no',
      '',
      'Audit-only: no delete, permission change, move, or rename was executed.'
    ]);
  } catch (err) {
    Logger.log('Tool run log update skipped: ' + err.message);
  }
}

function ccSealBuildContext_() {
  const artstudioFolder = DriveApp.getFolderById(CONFIG.artstudioFolderId);
  const controlCenterFolder = DriveApp.getFolderById(CONFIG.controlCenterFolderId);
  const reorganizationSpreadsheet = ccSealFindSpreadsheetByName_(controlCenterFolder, CONFIG.reorganizationPlanName);
  let artstudioParentFolder = null;
  const parents = artstudioFolder.getParents();
  if (parents.hasNext()) {
    artstudioParentFolder = parents.next();
  }
  return {
    artstudioFolder: artstudioFolder,
    artstudioParentFolder: artstudioParentFolder,
    controlCenterFolder: controlCenterFolder,
    reorganizationSpreadsheet: reorganizationSpreadsheet
  };
}

function ccSealValidateConfig_() {
  if (!CONFIG.artstudioFolderId || !CONFIG.controlCenterFolderId) {
    throw new Error('ARTSTUDIO and 00_CONTROL_CENTER folder IDs are required.');
  }
  if (CONFIG.allowDelete) {
    throw new Error('allowDelete must remain false for Stage 1 sealing.');
  }
  if (!CONFIG.dryRun || CONFIG.executeAcceptedActions) {
    throw new Error('Stage 1 production release is audit-only: dryRun must be true and executeAcceptedActions must be false.');
  }
  if (CONFIG.canonicalControlFiles.length !== 11) {
    throw new Error('Expected exactly 11 canonical control center files.');
  }
}

function ccSealScanFolderRecursive_(folder, locationType, depth, insideArtstudio) {
  const currentLocation = folder.getId() === CONFIG.controlCenterFolderId ? '00_CONTROL_CENTER' : locationType;
  const records = [
    ccSealDescribeObject_(folder, 'folder', currentLocation, null, insideArtstudio || currentLocation === '00_CONTROL_CENTER')
  ];

  const files = folder.getFiles();
  while (files.hasNext()) {
    records.push(ccSealDescribeObject_(files.next(), 'file', currentLocation, folder, true));
  }

  if (depth >= CONFIG.maxScanDepth) {
    return records;
  }

  const folders = folder.getFolders();
  while (folders.hasNext()) {
    const nestedFolder = folders.next();
    const nestedLocation = currentLocation === '00_CONTROL_CENTER' || nestedFolder.getId() === CONFIG.controlCenterFolderId
      ? '00_CONTROL_CENTER'
      : currentLocation;
    records.push.apply(records, ccSealScanFolderRecursive_(nestedFolder, nestedLocation, depth + 1, true));
  }
  return ccSealDedupeRecords_(records);
}

function ccSealDescribeObject_(object, objectType, locationType, parentFolder, insideArtstudioOverride) {
  const parentInfo = ccSealParentInfo_(object, parentFolder);
  const objectId = object.getId();
  const insideControlCenter = locationType === '00_CONTROL_CENTER' ||
    parentInfo.id === CONFIG.controlCenterFolderId ||
    objectId === CONFIG.controlCenterFolderId;
  const insideArtstudio = Boolean(insideArtstudioOverride) ||
    insideControlCenter ||
    parentInfo.id === CONFIG.artstudioFolderId ||
    objectId === CONFIG.artstudioFolderId;
  return {
    objectId: objectId,
    objectName: object.getName(),
    objectType: objectType,
    mimeType: objectType === 'file' ? object.getMimeType() : 'application/vnd.google-apps.folder',
    url: object.getUrl(),
    parentId: parentInfo.id,
    parentName: parentInfo.name,
    currentLocation: parentInfo.name || '',
    locationType: locationType,
    isInsideArtstudio: insideArtstudio,
    isInsideControlCenter: insideControlCenter,
    isRootLevelProjectFile: false,
    createdTime: ccSealDate_(object.getDateCreated()),
    modifiedTime: object.getLastUpdated ? ccSealDate_(object.getLastUpdated()) : '',
    notes: ''
  };
}

function ccSealParentInfo_(object, parentFolder) {
  if (parentFolder) {
    return { id: parentFolder.getId(), name: parentFolder.getName() };
  }
  const parents = object.getParents();
  if (parents.hasNext()) {
    const parent = parents.next();
    return { id: parent.getId(), name: parent.getName() };
  }
  return { id: '', name: '' };
}

function ccSealBuildRecommendations_(duplicateFindings, setupFindings, methodologyFindings, namingFindings) {
  return []
    .concat(duplicateFindings)
    .concat(setupFindings)
    .concat(methodologyFindings)
    .concat(namingFindings);
}

function ccSealNamingFinding_(record, rule, problem, targetName, recommendation) {
  return {
    object: record,
    detectionRule: rule,
    problem: problem,
    recommendedAction: 'rename after approval',
    targetName: targetName,
    targetLocation: record.currentLocation,
    machineRecommendation: recommendation,
    safeAction: 'rename after accepted decision',
    priority: 'P2',
    risk: 'medium',
    compareResult: 'not applicable',
    uniqueContentRisk: 'low'
  };
}

function ccSealDetectEbookIssue_(record, findings) {
  if (/e[\s_-]?book/i.test(record.objectName) && record.objectName.indexOf('E-book') === -1) {
    findings.push(ccSealNamingFinding_(record, 'INCONSISTENT_EBOOK_CASE',
      'E-book/e-book/Ebook naming is inconsistent.',
      record.objectName.replace(/e[\s_-]?book/ig, 'E-book'),
      'Normalize E-book naming after human approval.'));
  }
}

function ccSealLooksLikeSystemFolder_(name) {
  if (name === CONFIG.controlCenterFolderName || name === 'RU' || name === 'EN') {
    return false;
  }
  return /^(control|archive|setup|project|methodology|knowledge|source|legal|standard|system|file|document|base|рынок|стандарт|архив|источник)/i.test(name) ||
    ccSealHasCyrillic_(name);
}

function ccSealSuggestedName_(name) {
  if (name === '00_Legal_Files') {
    return '07_Legal_Files';
  }
  if (name === 'Стандарты' || name === 'РЎС‚Р°РЅРґР°СЂС‚С‹') {
    return '08_Standards';
  }
  return name.replace(/^00_/, 'NN_').replace(/\s+/g, '_');
}

function ccSealHasCyrillic_(value) {
  return /[\u0400-\u04FF]/.test(value);
}

function ccSealHasLatin_(value) {
  return /[A-Za-z]/.test(value);
}

function ccSealIsProjectObjectName_(name) {
  if (CONFIG.canonicalControlFiles.indexOf(name) !== -1) {
    return true;
  }
  if (CONFIG.setupArtifacts.map(function(item) { return item.toLowerCase(); }).indexOf(name.toLowerCase()) !== -1) {
    return true;
  }
  return name.indexOf(CONFIG.methodologyPrefix) === 0 || name.indexOf('ARTSTUDIO Base вЂ—') === 0;
}

function ccSealFindSpreadsheetByName_(folder, name) {
  const files = folder.getFilesByName(name);
  while (files.hasNext()) {
    const file = files.next();
    if (file.getMimeType() === MimeType.GOOGLE_SHEETS) {
      return SpreadsheetApp.openById(file.getId());
    }
  }
  throw new Error('Spreadsheet not found in folder ' + folder.getName() + ': ' + name);
}

function ccSealEnsureSheet_(spreadsheet, sheetName, headers) {
  let sheet = spreadsheet.getSheetByName(sheetName);
  if (!sheet) {
    sheet = spreadsheet.insertSheet(sheetName);
  }
  const currentHeaders = ccSealGetHeaders_(sheet);
  if (!currentHeaders.length) {
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  } else {
    headers.forEach(function(header) {
      if (currentHeaders.indexOf(header) === -1) {
        sheet.getRange(1, sheet.getLastColumn() + 1).setValue(header);
        currentHeaders.push(header);
      }
    });
  }
  sheet.setFrozenRows(1);
  return sheet;
}

function ccSealResetSheet_(spreadsheet, sheetName, headers) {
  let sheet = spreadsheet.getSheetByName(sheetName);
  if (!sheet) {
    sheet = spreadsheet.insertSheet(sheetName);
  }
  sheet.clear();
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  sheet.setFrozenRows(1);
  return sheet;
}

function ccSealGetHeaders_(sheet) {
  if (sheet.getLastColumn() < 1 || sheet.getLastRow() < 1) {
    return [];
  }
  return sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0].map(function(value) {
    return String(value || '').trim();
  });
}

function ccSealWriteRows_(sheet, rows) {
  if (!rows.length) {
    return;
  }
  sheet.getRange(sheet.getLastRow() + 1, 1, rows.length, rows[0].length).setValues(rows);
}

function ccSealReadExistingRecommendationKeys_(sheet, headers) {
  const objectIdIndex = headers.indexOf('Object ID');
  const ruleIndex = headers.indexOf('Detection rule');
  const keys = {};
  if (objectIdIndex === -1 || ruleIndex === -1 || sheet.getLastRow() < 2) {
    return keys;
  }
  const values = sheet.getRange(2, 1, sheet.getLastRow() - 1, headers.length).getValues();
  values.forEach(function(row) {
    const objectId = row[objectIdIndex];
    const rule = row[ruleIndex];
    if (objectId && rule) {
      keys[ccSealKey_(objectId, rule)] = true;
    }
  });
  return keys;
}

function ccSealReadDecisionMap_(spreadsheet, sheetName) {
  const sheet = spreadsheet.getSheetByName(sheetName);
  const decisions = {};
  if (!sheet || sheet.getLastRow() < 2) {
    return decisions;
  }
  const headers = ccSealGetHeaders_(sheet);
  const objectIdIndex = headers.indexOf('Object ID');
  const ruleIndex = headers.indexOf('Detection rule');
  const decisionIndex = headers.indexOf('Human decision');
  if (objectIdIndex === -1 || ruleIndex === -1 || decisionIndex === -1) {
    return decisions;
  }
  const values = sheet.getRange(2, 1, sheet.getLastRow() - 1, headers.length).getValues();
  values.forEach(function(row) {
    if (row[objectIdIndex] && row[ruleIndex] && row[decisionIndex]) {
      decisions[ccSealKey_(row[objectIdIndex], row[ruleIndex])] = row[decisionIndex];
    }
  });
  return decisions;
}

function ccSealRowFromMap_(headers, valuesByHeader) {
  return headers.map(function(header) {
    return Object.prototype.hasOwnProperty.call(valuesByHeader, header) ? valuesByHeader[header] : '';
  });
}

function ccSealDedupeRecords_(records) {
  const seen = {};
  return records.filter(function(record) {
    const key = record.objectId + '|' + record.parentId + '|' + record.locationType;
    if (seen[key]) {
      return false;
    }
    seen[key] = true;
    return true;
  });
}

function ccSealDedupeFindings_(findings) {
  const seen = {};
  return findings.filter(function(finding) {
    const key = ccSealKey_(finding.object.objectId, finding.detectionRule);
    if (seen[key]) {
      return false;
    }
    seen[key] = true;
    return true;
  });
}

function ccSealKey_(objectId, detectionRule) {
  return String(objectId) + '|' + String(detectionRule);
}

function ccSealActionId_(rule, objectId) {
  return 'SEAL-' + rule.replace(/[^A-Z0-9]+/g, '-').replace(/-$/, '') + '-' + String(objectId).slice(0, 8);
}

function ccSealValidationRow_(id, name, expected, actual, status, notes, checkedAt) {
  return [id, name, expected, actual, status, notes || '', checkedAt];
}

function ccSealIsSafeMode_() {
  return CONFIG.dryRun === true && CONFIG.executeAcceptedActions === false && CONFIG.allowDelete === false;
}

function ccSealBool_(value) {
  return value ? 'yes' : 'no';
}

function ccSealNow_() {
  return Utilities.formatDate(new Date(), CONFIG.timezone, "yyyy-MM-dd'T'HH:mm:ss");
}

function ccSealDate_(date) {
  return date ? Utilities.formatDate(date, CONFIG.timezone, "yyyy-MM-dd'T'HH:mm:ss") : '';
}
