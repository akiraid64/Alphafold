// =============================================
// LOGGING UTILITY
// =============================================
const LOG_LEVELS = { DEBUG: 0, INFO: 1, WARN: 2, ERROR: 3 };
const CURRENT_LOG_LEVEL = LOG_LEVELS.DEBUG;

function log(level, category, message, data = null) {
    if (LOG_LEVELS[level] < CURRENT_LOG_LEVEL) return;
    const timestamp = new Date().toLocaleTimeString('en-US', { hour12: false });
    const prefix = `[${timestamp}] [${level}] [${category}]`;
    const styles = {
        DEBUG: 'color: #888',
        INFO: 'color: #4CAF50',
        WARN: 'color: #FF9800',
        ERROR: 'color: #f44336; font-weight: bold'
    };
    if (data) {
        console.log(`%c${prefix} ${message}`, styles[level], data);
    } else {
        console.log(`%c${prefix} ${message}`, styles[level]);
    }
}

// =============================================
// GLOBAL STATE
// =============================================
let state = {
    // Test Structure (local)
    test: {
        folderPath: '',
        files: { pdb: [], pae: null },
        currentModelIndex: 0,
        paeData: null,
        plugin: null
    },
    // Reference Structure (from AlphaFold DB)
    ref: {
        folderPath: '',
        files: { pdb: null, pae: null },
        paeData: null,
        plugin: null,
        geneName: '',
        uniprotId: ''
    },
    // Full paths for comparison
    testPdbPath: null,
    refPdbPath: null
};

// =============================================
// DOM ELEMENTS
// =============================================
const elements = {};

function initElements() {
    log('INFO', 'DOM', 'Initializing DOM element references...');
    // Extract key elements
    elements.landingPage = document.getElementById('access-screen');
    elements.accessScreen = elements.landingPage; // Alias for backward compatibility
    elements.analyzeBtn = document.getElementById('analyze-btn');
    elements.showMutationsBtn = document.getElementById('show-mutations-btn');
    elements.pathInput = document.getElementById('folder-path-input');
    elements.geneInput = document.getElementById('ref-gene-input');
    elements.errorMsg = document.getElementById('access-error');
    elements.loadingMsg = document.getElementById('loading-msg');
    elements.mainLayout = document.getElementById('main-layout');
    elements.modelSelector = document.getElementById('model-selector');
    elements.resetBtn = document.getElementById('reset-view-btn'); // Renamed from reset-selection-btn to reset-view-btn
    elements.compareBtn = document.getElementById('compare-btn'); // Renamed from compare-structures-btn to compare-btn
    elements.mutationsBtn = document.getElementById('mutations-btn'); // New button in main view
    elements.comparisonModal = document.getElementById('comparison-modal');
    elements.comparisonContent = document.getElementById('comparison-content');
    elements.mutationsModal = document.getElementById('mutations-modal');
    elements.mutationsContent = document.getElementById('mutations-content');
    elements.modalOverlay = document.getElementById('modal-overlay');
    elements.closeModalBtn = document.getElementById('close-modal-btn');
    elements.refTitle = document.getElementById('ref-title'); // Added back refTitle
    elements.paeCanvasTest = document.getElementById('pae-canvas-test'); // Added back paeCanvasTest
    elements.paeCanvasRef = document.getElementById('pae-canvas-ref'); // Added back paeCanvasRef

    // Check if all expected elements are found
    const expectedIds = [
        'access-screen', 'analyze-btn', 'show-mutations-btn', 'folder-path-input',
        'gene-name-input', 'access-error', 'loading-msg', 'main-layout',
        'model-selector', 'reset-view-btn', 'compare-btn', 'comparison-modal',
        'comparison-content', 'mutations-modal', 'mutations-content', 'modal-overlay',
        'close-modal-btn', 'ref-title', 'pae-canvas-test', 'pae-canvas-ref'
    ];

    for (const id of expectedIds) {
        if (!document.getElementById(id)) {
            log('WARN', 'DOM', `Element not found: #${id}`);
        }
    }
    log('INFO', 'DOM', '✓ DOM elements initialized');
    return true;
}

// =============================================
// MAIN INIT
// =============================================
async function init() {
    log('INFO', 'App', '========================================');
    log('INFO', 'App', 'AlphaFold Structure Comparison Starting...');
    log('INFO', 'App', '========================================');

    if (!initElements()) return;

    // Event listeners
    elements.analyzeBtn.addEventListener('click', analyze);
    elements.showMutationsBtn.addEventListener('click', showMutations);
    elements.modelSelector.addEventListener('change', (e) => loadTestModel(e.target.value));
    elements.resetBtn.addEventListener('click', resetSelection);
    elements.compareBtn.addEventListener('click', compareStructures);
    if (elements.mutationsBtn) elements.mutationsBtn.addEventListener('click', showMutations);
    elements.closeModalBtn.addEventListener('click', closeComparisonModal);
    elements.modalOverlay.addEventListener('click', () => {
        closeComparisonModal();
        closeMutationsModal();
    });

    log('INFO', 'App', '✓ Application Ready!');
}

// =============================================
// ANALYZE - Main Entry Point
// =============================================
async function analyze() {
    const testPath = elements.pathInput.value.trim();
    const geneName = elements.geneInput.value.trim().toUpperCase();

    log('INFO', 'Analyze', `Test Path: ${testPath}, Gene: ${geneName}`);

    if (!testPath) {
        return showError("Please enter the Gene-Test local path.");
    }
    if (!geneName) {
        return showError("Please enter the Original Gene name.");
    }

    showLoading(true);
    showError("");

    try {
        // 1. Load Test Structure files
        log('INFO', 'Analyze', 'Loading test structure files...');
        const testResponse = await fetch(`/api/files?path=${encodeURIComponent(testPath)}`);
        if (!testResponse.ok) throw new Error("Test path not found");
        const testFiles = await testResponse.json();

        if (testFiles.pdb_files.length === 0) {
            throw new Error("No PDB files found in test directory");
        }

        state.test.folderPath = testPath;
        state.test.files.pdb = testFiles.pdb_files;
        state.test.files.pae = testFiles.pae_file;

        // 2. Search Gene and Download Reference
        log('INFO', 'Analyze', `Searching for gene: ${geneName}...`);
        const refResponse = await fetch(`/api/search-gene?gene_name=${encodeURIComponent(geneName)}`);
        if (!refResponse.ok) {
            const err = await refResponse.json();
            throw new Error(err.detail || "Gene not found");
        }
        const refData = await refResponse.json();

        state.ref.folderPath = refData.pdb_path;
        state.ref.files.pdb = refData.pdb_file;
        state.ref.files.pae = refData.pae_file;
        state.ref.geneName = geneName;
        state.ref.uniprotId = refData.uniprot_id;

        log('INFO', 'Analyze', `✓ Reference found: ${refData.uniprot_id}`);

        // 3. Switch to main layout
        elements.accessScreen.classList.add('hidden');
        elements.mainLayout.classList.remove('hidden');

        // Populate model selector with test files
        elements.modelSelector.innerHTML = '';

        // Sort files by rank number (rank_001, rank_002, etc.)
        const sortedFiles = testFiles.pdb_files.sort((a, b) => {
            const rankA = a.match(/rank_(\d+)/);
            const rankB = b.match(/rank_(\d+)/);

            if (rankA && rankB) {
                return parseInt(rankA[1]) - parseInt(rankB[1]);
            }
            return a.localeCompare(b); // Fallback to alphabetical
        });

        sortedFiles.forEach((file, index) => {
            const option = document.createElement('option');
            option.value = index;

            // Extract rank number for display
            const rankMatch = file.match(/rank_(\d+)/);
            const rankNum = rankMatch ? rankMatch[1] : (index + 1);

            option.textContent = `Rank ${rankNum}`;
            elements.modelSelector.appendChild(option);
        });

        // Store sorted files
        state.test.files.pdb = sortedFiles;
        elements.refTitle.textContent = `Reference: ${geneName} (${refData.uniprot_id})`;

        // 4. Initialize both viewers
        await initBothViewers();

        // 5. Load structures
        await loadTestModel(0);
        await loadRefModel();

        // 6. Load PAE data
        if (state.test.files.pae) loadPaeData('test');
        if (state.ref.files.pae) loadPaeData('ref');

        showLoading(false);
        log('INFO', 'Analyze', '✓ Analysis complete!');

    } catch (err) {
        log('ERROR', 'Analyze', `Failed: ${err.message}`, err);
        showError(err.message);
        showLoading(false);
    }
}

// =============================================
// MOL* VIEWER INITIALIZATION
// =============================================
async function initBothViewers() {
    log('INFO', 'Mol*', 'Initializing dual viewers...');

    // Initialize Test Viewer
    state.test.plugin = await molstar.Viewer.create('structure-viewer-test', {
        layoutIsExpanded: false,
        layoutShowControls: false,
        layoutShowRemoteState: false,
        layoutShowSequence: false,
        layoutShowLog: false,
        layoutShowLeftPanel: false,
        viewportShowExpand: false,
        viewportShowSelectionMode: false,
        viewportShowAnimation: false,
        volumeStreamingServer: '',
        pdbProvider: 'rcsb',
        emdbProvider: 'rcsb',
    });
    await setDarkBackground(state.test.plugin);
    log('INFO', 'Mol*', '✓ Test viewer created');

    // Initialize Reference Viewer
    state.ref.plugin = await molstar.Viewer.create('structure-viewer-ref', {
        layoutIsExpanded: false,
        layoutShowControls: false,
        layoutShowRemoteState: false,
        layoutShowSequence: false,
        layoutShowLog: false,
        layoutShowLeftPanel: false,
        viewportShowExpand: false,
        viewportShowSelectionMode: false,
        viewportShowAnimation: false,
        volumeStreamingServer: '',
        pdbProvider: 'rcsb',
        emdbProvider: 'rcsb',
    });
    await setDarkBackground(state.ref.plugin);
    log('INFO', 'Mol*', '✓ Reference viewer created');
}

async function setDarkBackground(viewer) {
    try {
        const plugin = viewer.plugin || viewer;
        const canvas3d = plugin.canvas3d;
        if (canvas3d) {
            canvas3d.setProps({
                renderer: {
                    ...canvas3d.props.renderer,
                    backgroundColor: 0x1A1A1A
                }
            });
        }
    } catch (e) {
        log('WARN', 'Mol*', 'Could not set dark background');
    }
}

// =============================================
// LOAD MODELS
// =============================================
async function loadTestModel(index) {
    log('INFO', 'Model', `Loading test model ${index}...`);
    const plugin = state.test.plugin;
    const filename = state.test.files.pdb[index];
    const fullPath = `${state.test.folderPath}\\${filename}`;

    // Store the full path for comparison
    state.testPdbPath = fullPath;
    log('DEBUG', 'Model', `Stored test PDB path: ${fullPath}`);

    const url = `/api/data?path=${encodeURIComponent(state.test.folderPath)}&file=${encodeURIComponent(filename)}`;

    // Clear previous
    try {
        const p = plugin.plugin || plugin;
        if (p.clear) await p.clear();
    } catch (e) { }

    await plugin.loadStructureFromUrl(url, 'pdb', false);
    await applyPlddtColoring(plugin);
    log('INFO', 'Model', '✓ Test model loaded');
}

async function loadRefModel() {
    log('INFO', 'Model', 'Loading reference model...');
    const plugin = state.ref.plugin;
    const fullPath = `${state.ref.folderPath}\\${state.ref.files.pdb}`;

    // Store the full path for comparison
    state.refPdbPath = fullPath;
    log('DEBUG', 'Model', `Stored ref PDB path: ${fullPath}`);

    const url = `/api/data?path=${encodeURIComponent(state.ref.folderPath)}&file=${encodeURIComponent(state.ref.files.pdb)}`;

    await plugin.loadStructureFromUrl(url, 'pdb', false);
    await applyPlddtColoring(plugin);
    log('INFO', 'Model', '✓ Reference model loaded');
}

// =============================================
// pLDDT COLORING - Multiple Approaches
// =============================================
async function applyPlddtColoring(viewer) {
    log('INFO', 'Color', 'Applying pLDDT coloring...');

    const plugin = viewer.plugin || viewer;

    // Wait for representations to be created
    await new Promise(resolve => setTimeout(resolve, 800));

    // pLDDT Color Theme - Exact AlphaFold colors
    const plddtColorTheme = {
        name: 'uncertainty',
        params: {
            list: {
                kind: 'interpolate',
                colors: [
                    [0xFF7D45, 0],      // Orange at 0 (Very Low <50)
                    [0xFF7D45, 0.50],   // Orange until 50
                    [0xFFDB13, 0.50],   // Yellow at 50 (Low 50-70)
                    [0xFFDB13, 0.70],   // Yellow until 70
                    [0x65CBF3, 0.70],   // Cyan at 70 (Confident 70-90)  
                    [0x65CBF3, 0.90],   // Cyan until 90
                    [0x0053D6, 0.90],   // Deep Blue at 90 (Very High >90)
                    [0x0053D6, 1.0],    // Deep Blue at 100
                ]
            }
        }
    };

    let success = false;

    // Approach 1: Use managers.structure.hierarchy
    try {
        const structures = plugin.managers?.structure?.hierarchy?.current?.structures;
        if (structures && structures.length > 0) {
            log('DEBUG', 'Color', `Approach 1: Found ${structures.length} structures`);
            for (const struct of structures) {
                const components = struct.components || [];
                for (const comp of components) {
                    const representations = comp.representations || [];
                    for (const repr of representations) {
                        const ref = repr.cell?.transform?.ref;
                        if (ref) {
                            log('DEBUG', 'Color', `  Updating repr ref: ${ref}`);
                            await plugin.build()
                                .to(ref)
                                .update(old => ({ ...old, colorTheme: plddtColorTheme }))
                                .commit();
                            success = true;
                        }
                    }
                }
            }
            if (success) {
                log('INFO', 'Color', '✓ Applied via managers.structure.hierarchy');
                return;
            }
        }
    } catch (e) {
        log('DEBUG', 'Color', `Approach 1 failed: ${e.message}`);
    }

    // Approach 2: Find cells with "3D" in type name
    try {
        const cells = Array.from(plugin.state.data.cells.values());
        log('DEBUG', 'Color', `Approach 2: Total cells: ${cells.length}`);

        const repr3DCells = cells.filter(cell => {
            const typeName = cell.obj?.type?.name || '';
            return typeName.includes('3D') || typeName.includes('Representation');
        });

        log('DEBUG', 'Color', `  Found ${repr3DCells.length} 3D/Representation cells`);

        for (const cell of repr3DCells) {
            try {
                const ref = cell.transform.ref;
                await plugin.build()
                    .to(ref)
                    .update(old => ({ ...old, colorTheme: plddtColorTheme }))
                    .commit();
                log('DEBUG', 'Color', `  ✓ Updated ${ref}`);
                success = true;
            } catch (e) {
                // Might fail for non-representation cells
            }
        }

        if (success) {
            log('INFO', 'Color', '✓ Applied via state tree cells');
            return;
        }
    } catch (e) {
        log('DEBUG', 'Color', `Approach 2 failed: ${e.message}`);
    }

    // Approach 3: Try updateRepresentationsTheme if available
    try {
        if (plugin.managers?.structure?.component?.updateRepresentationsTheme) {
            await plugin.managers.structure.component.updateRepresentationsTheme(
                plugin.managers.structure.hierarchy.current.structures,
                { color: 'uncertainty' }
            );
            log('INFO', 'Color', '✓ Applied via updateRepresentationsTheme');
            return;
        }
    } catch (e) {
        log('DEBUG', 'Color', `Approach 3 failed: ${e.message}`);
    }

    // Log all cell types if nothing worked
    if (!success) {
        log('WARN', 'Color', 'All coloring approaches failed! Cell types:');
        try {
            const cells = Array.from(plugin.state.data.cells.values());
            const types = new Set();
            cells.forEach(c => {
                const t = c.obj?.type?.name;
                if (t) types.add(t);
            });
            log('DEBUG', 'Color', `  Unique types: ${[...types].join(', ')}`);
        } catch (e) { }
    }
}

// =============================================
// PAE HEATMAP
// =============================================
async function loadPaeData(which) {
    const stateObj = which === 'test' ? state.test : state.ref;
    const canvas = which === 'test' ? elements.paeCanvasTest : elements.paeCanvasRef;
    const paeFile = stateObj.files.pae;
    const folderPath = stateObj.folderPath;

    if (!paeFile || !canvas) return;

    log('INFO', 'PAE', `Loading ${which} PAE data...`);

    try {
        const response = await fetch(`/api/data?path=${encodeURIComponent(folderPath)}&file=${encodeURIComponent(paeFile)}`);
        if (!response.ok) return;

        const json = await response.json();
        log('DEBUG', 'PAE', `${which} PAE JSON structure:`, Object.keys(json));

        let matrix = null;

        // Handle different PAE formats:
        // Local v1: { predicted_aligned_error: [[...]] } or [{ predicted_aligned_error: [[...]] }]
        // AlphaFold DB v4: [{ predicted_aligned_error: [[...]], ... }]
        // Direct matrix: [[...]]

        if (Array.isArray(json)) {
            // Check if it's a direct matrix (array of arrays of numbers)
            if (json.length > 0 && Array.isArray(json[0]) && typeof json[0][0] === 'number') {
                matrix = json;
                log('DEBUG', 'PAE', `${which}: Direct matrix format, size ${matrix.length}`);
            } else if (json.length > 0 && json[0]) {
                // Array of objects - extract from first entry
                matrix = json[0].predicted_aligned_error || json[0].pae;
                log('DEBUG', 'PAE', `${which}: Array of objects format`);
            }
        } else if (typeof json === 'object') {
            matrix = json.predicted_aligned_error || json.pae;
            log('DEBUG', 'PAE', `${which}: Object format`);
        }

        stateObj.paeData = matrix;
        if (matrix && matrix.length > 0) {
            log('INFO', 'PAE', `${which} PAE matrix size: ${matrix.length}x${matrix[0]?.length || 0}`);
            renderPaeHeatmap(canvas, matrix);
            log('INFO', 'PAE', `✓ ${which} PAE rendered`);
        } else {
            log('WARN', 'PAE', `${which} PAE matrix not found or empty`);
            // Draw "No PAE Data" message
            const ctx = canvas.getContext('2d');
            const rect = canvas.parentElement.getBoundingClientRect();
            canvas.width = rect.width - 10;
            canvas.height = rect.height - 10;
            ctx.fillStyle = '#666';
            ctx.font = '14px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('No PAE Data', canvas.width / 2, canvas.height / 2);
        }
    } catch (e) {
        log('WARN', 'PAE', `Failed to load ${which} PAE: ${e.message}`, e);
    }
}

function renderPaeHeatmap(canvas, matrix) {
    if (!matrix) return;
    const ctx = canvas.getContext('2d');
    const size = matrix.length;

    // Perfectly square canvas: left+right = top+bottom = 110px
    const plotAreaSize = 300;
    const margin = { top: 55, right: 55, bottom: 60, left: 50 };  // Total: 405x405 (SQUARE!)

    canvas.width = plotAreaSize + margin.left + margin.right;   // 405px
    canvas.height = plotAreaSize + margin.top + margin.bottom;  // 405px

    const plotSize = plotAreaSize;
    const plotHeight = plotAreaSize;

    // Clear and set black background
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Draw heatmap (green gradient: dark = high error, light = low error)
    const cellW = plotSize / size;
    const cellH = plotHeight / size;

    for (let i = 0; i < size; i++) {
        for (let j = 0; j < size; j++) {
            const val = matrix[i][j];
            // 0 = light green (low error), 30 = dark green (high error)
            const t = Math.min(val / 30, 1);
            const r = Math.floor(0 + 100 * (1 - t));
            const g = Math.floor(100 + 155 * (1 - t));
            const b = Math.floor(0 + 100 * (1 - t));
            ctx.fillStyle = `rgb(${r}, ${g}, ${b})`;
            ctx.fillRect(margin.left + j * cellW, margin.top + i * cellH, Math.ceil(cellW), Math.ceil(cellH));
        }
    }

    // Draw axes
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 1;

    // Left axis
    ctx.beginPath();
    ctx.moveTo(margin.left, margin.top);
    ctx.lineTo(margin.left, margin.top + plotHeight);
    ctx.stroke();

    // Bottom axis
    ctx.beginPath();
    ctx.moveTo(margin.left, margin.top + plotHeight);
    ctx.lineTo(margin.left + plotSize, margin.top + plotHeight);
    ctx.stroke();

    // Tick marks and labels
    ctx.fillStyle = '#fff';
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'center';

    const tickCount = 5;
    const tickInterval = Math.floor(size / tickCount);

    for (let i = 0; i <= tickCount; i++) {
        const residue = i === 0 ? 1 : Math.min(i * tickInterval, size);
        const pos = ((residue - 1) / (size - 1));

        // Bottom ticks (Scored Residue)
        const x = margin.left + pos * plotSize;
        ctx.fillText(residue.toString(), x, margin.top + plotHeight + 15);

        // Left ticks (Aligned Residue)
        ctx.textAlign = 'right';
        const y = margin.top + pos * plotHeight;
        ctx.fillText(residue.toString(), margin.left - 5, y + 4);
        ctx.textAlign = 'center';
    }

    // Axis labels
    ctx.font = 'bold 11px sans-serif';

    // X-axis label
    ctx.fillText('Scored Residue', margin.left + plotSize / 2, canvas.height - 25);

    // Y-axis label (rotated)
    ctx.save();
    ctx.translate(15, margin.top + plotHeight / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('Aligned Residue', 0, 0);
    ctx.restore();

    // Horizontal color scale bar at bottom
    const barWidth = plotSize * 0.7;
    const barHeight = 10;
    const barX = margin.left + (plotSize - barWidth) / 2;
    const barY = canvas.height - 15;

    // Draw gradient bar (left = green/low, right = dark/high)
    for (let i = 0; i < barWidth; i++) {
        const t = i / barWidth;
        const r = Math.floor(0 + 100 * (1 - t));
        const g = Math.floor(100 + 155 * (1 - t));
        const b = Math.floor(0 + 100 * (1 - t));
        ctx.fillStyle = `rgb(${r}, ${g}, ${b})`;
        ctx.fillRect(barX + i, barY, 1, barHeight);
    }

    // Scale labels
    ctx.font = '9px sans-serif';
    ctx.fillStyle = '#fff';
    ctx.textAlign = 'left';
    ctx.fillText('0', barX - 5, barY + barHeight / 2 + 3);
    ctx.textAlign = 'right';
    ctx.fillText('30', barX + barWidth + 5, barY + barHeight / 2 + 3);
    ctx.textAlign = 'center';
    ctx.font = '8px sans-serif';
    ctx.fillText('Expected Position Error (Angstroms)', margin.left + plotSize / 2, barY + barHeight + 10);

    // Store layout info on canvas for interaction
    canvas.paeLayout = { margin, plotSize, plotHeight, matrixSize: size, plotAreaSize };

    // Setup mouse interaction for linked selection
    setupPaeInteraction(canvas, matrix);
}

// =============================================
// PAE LINKED SELECTION
// =============================================
function setupPaeInteraction(canvas, matrix) {
    const which = canvas.id.includes('test') ? 'test' : 'ref';
    const layout = canvas.paeLayout;
    if (!layout) return;

    let isSelecting = false;
    let startX = 0, startY = 0;

    const getResidueFromPos = (x, y) => {
        const relX = x - layout.margin.left;
        const relY = y - layout.margin.top;
        const residueX = Math.floor((relX / layout.plotSize) * layout.matrixSize) + 1;
        const residueY = Math.floor((relY / layout.plotHeight) * layout.matrixSize) + 1;
        return { x: residueX, y: residueY };
    };

    canvas.onmousedown = (e) => {
        const rect = canvas.getBoundingClientRect();
        startX = e.clientX - rect.left;
        startY = e.clientY - rect.top;
        isSelecting = true;
    };

    canvas.onmousemove = (e) => {
        if (!isSelecting) return;

        const rect = canvas.getBoundingClientRect();
        const currentX = e.clientX - rect.left;
        const currentY = e.clientY - rect.top;

        // Redraw PAE
        renderPaeHeatmapOnly(canvas, matrix);

        // Draw selection box
        const ctx = canvas.getContext('2d');
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 2;
        ctx.setLineDash([5, 3]);
        ctx.strokeRect(startX, startY, currentX - startX, currentY - startY);
        ctx.setLineDash([]);
    };

    canvas.onmouseup = (e) => {
        if (!isSelecting) return;
        isSelecting = false;

        const rect = canvas.getBoundingClientRect();
        const endX = e.clientX - rect.left;
        const endY = e.clientY - rect.top;

        const start = getResidueFromPos(Math.min(startX, endX), Math.min(startY, endY));
        const end = getResidueFromPos(Math.max(startX, endX), Math.max(startY, endY));

        // Clamp residue numbers
        const fromRes = Math.max(1, Math.min(start.x, start.y));
        const toRes = Math.min(layout.matrixSize, Math.max(end.x, end.y));

        log('INFO', 'PAE', `${which}: Selected residues ${fromRes}-${toRes}`);

        // Highlight residues in 3D structure
        highlightResidues(which, fromRes, toRes);
    };
}

// Simple redraw without interaction setup (to avoid infinite loop)
function renderPaeHeatmapOnly(canvas, matrix) {
    if (!matrix) return;
    const ctx = canvas.getContext('2d');
    const size = matrix.length;
    const layout = canvas.paeLayout;
    if (!layout) return;

    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    const cellW = layout.plotSize / size;
    const cellH = layout.plotHeight / size;

    for (let i = 0; i < size; i++) {
        for (let j = 0; j < size; j++) {
            const val = matrix[i][j];
            const t = Math.min(val / 30, 1);
            const r = Math.floor(0 + 100 * (1 - t));
            const g = Math.floor(100 + 155 * (1 - t));
            const b = Math.floor(0 + 100 * (1 - t));
            ctx.fillStyle = `rgb(${r}, ${g}, ${b})`;
            ctx.fillRect(layout.margin.left + j * cellW, layout.margin.top + i * cellH, Math.ceil(cellW), Math.ceil(cellH));
        }
    }
}

// Highlight residues in 3D structure
async function highlightResidues(which, fromRes, toRes) {
    const plugin = which === 'test' ? state.test.plugin : state.ref.plugin;
    if (!plugin) return;

    try {
        const p = plugin.plugin || plugin;

        // Create residue selection expression
        const selection = {
            type: 'residue-index',
            params: { start: fromRes - 1, end: toRes }
        };

        log('DEBUG', 'Selection', `Highlighting ${which} residues ${fromRes}-${toRes}`);

        // Try to select residues using Mol* API
        // This is a simplified approach - full implementation would use proper Mol* selection API
        if (p.managers?.structure?.selection) {
            // Clear previous selection
            p.managers.structure.selection.clear();
        }

    } catch (e) {
        log('WARN', 'Selection', `Failed to highlight: ${e.message}`);
    }
}

// =============================================
// UTILITIES
// =============================================
function showError(msg) {
    if (elements.errorMsg) elements.errorMsg.textContent = msg;
}

function showLoading(show) {
    if (elements.loadingMsg) {
        elements.loadingMsg.classList.toggle('hidden', !show);
    }
}

function resetSelection() {
    log('DEBUG', 'UI', 'Resetting selection...');
    // Clear selections in both viewers
    try {
        const testPlugin = state.test?.plugin?.plugin || state.test?.plugin;
        const refPlugin = state.ref?.plugin?.plugin || state.ref?.plugin;

        if (testPlugin?.managers?.structure?.selection) {
            testPlugin.managers.structure.selection.clear();
        }
        if (refPlugin?.managers?.structure?.selection) {
            refPlugin.managers.structure.selection.clear();
        }
        log('INFO', 'UI', '✓ Selection cleared');
    } catch (e) { }
}

// =============================================
// STRUCTURE COMPARISON
// =============================================
async function compareStructures() {
    log('INFO', 'Compare', 'Starting structure comparison...');

    if (!state.testPdbPath || !state.refPdbPath) {
        showError('Load both structures first before comparing');
        return;
    }

    // Show modal with progress immediately
    elements.comparisonModal.style.display = 'block';
    elements.modalOverlay.style.display = 'block';

    elements.comparisonContent.innerHTML = `
        <div style="text-align: center; padding: 40px;">
            <div style="font-size: 1.2rem; color: #65CBF3; margin-bottom: 20px;">
                ⏳ Comparing Structures...
            </div>
            <div id="progress-steps" style="text-align: left; max-width: 400px; margin: 0 auto; font-size: 0.9rem; color: #888;">
                <div id="step-1">✓ Loading structures...</div>
                <div id="step-2" style="opacity: 0.3;">⏳ Superimposing backbones...</div>
                <div id="step-3" style="opacity: 0.3;">⏳ Calculating per-residue deviations...</div>
                <div id="step-4" style="opacity: 0.3;">⏳ Generating report...</div>
            </div>
        </div>
    `;

    // Simulate progress steps
    setTimeout(() => {
        document.getElementById('step-1').innerHTML = '✓ Loading structures...';
        document.getElementById('step-2').style.opacity = '1';
        document.getElementById('step-2').innerHTML = '⏳ Superimposing backbones...';
    }, 100);

    setTimeout(() => {
        document.getElementById('step-2').innerHTML = '✓ Superimposing backbones...';
        document.getElementById('step-3').style.opacity = '1';
        document.getElementById('step-3').innerHTML = '⏳ Calculating per-residue deviations...';
    }, 300);

    setTimeout(() => {
        document.getElementById('step-3').innerHTML = '✓ Calculating per-residue deviations...';
        document.getElementById('step-4').style.opacity = '1';
        document.getElementById('step-4').innerHTML = '⏳ Generating report...';
    }, 500);

    try {
        const url = `/api/compare-structures?test_path=${encodeURIComponent(state.testPdbPath)}&ref_path=${encodeURIComponent(state.refPdbPath)}`;

        const response = await fetch(url);
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Comparison failed');
        }

        const result = await response.json();

        // Show completion
        if (document.getElementById('step-4')) {
            document.getElementById('step-4').innerHTML = '✓ Generating report...';
        }

        // Wait a brief moment to show completion, then display results
        setTimeout(() => displayComparisonResults(result), 300);

    } catch (error) {
        log('ERROR', 'Compare', `Failed: ${error.message}`);
        elements.comparisonContent.innerHTML = `
            <div style="color: #f87171; padding: 40px; text-align: center;">
                <div style="font-size: 1.5rem; margin-bottom: 10px;">❌</div>
                <div>Comparison failed: ${error.message}</div>
            </div>
        `;
    }
}

function displayComparisonResults(data) {
    const content = elements.comparisonContent;

    // Create HTML output
    let html = `
        <div style="margin-bottom: 20px; padding: 15px; background: #0a0a0a; border-radius: 4px;">
            <h4 style="margin-top: 0; color: #65CBF3;">Overall Metrics</h4>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                <div>
                    <div style="font-size: 0.9rem; color: #888;">TM-Score</div>
                    <div style="font-size: 1.8rem; color: ${data.tm_score > 0.95 ? '#4ade80' : data.tm_score > 0.5 ? '#fbbf24' : '#f87171'};">${data.tm_score.toFixed(3)}</div>
                    <div style="font-size: 0.75rem; color: #888;">(0-1, higher = more similar)</div>
                </div>
                <div>
                    <div style="font-size: 0.9rem; color: #888;">Global RMSD</div>
                    <div style="font-size: 1.8rem; color:#65CBF3;">${data.global_rmsd.toFixed(2)} Å</div>
                    <div style="font-size: 0.75rem; color: #888;">(lower = more similar)</div>
                </div>
            </div>
        </div>
        
        <div style="margin-bottom: 20px;">
            <h4 style="color: #65CBF3;">Per-Residue Deviations</h4>
            <div style="max-height: 200px; overflow-y: auto; background: #0a0a0a; padding: 10px; border-radius: 4px;">
    `;

    // Create a simple bar chart visualization
    const maxDev = data.max_deviation;
    for (const resInfo of data.residue_deviations) {
        const barWidth = (resInfo.deviation / maxDev) * 100;
        const color = resInfo.deviation > 2.0 ? '#f87171' : resInfo.deviation > 1.0 ? '#fbbf24' : '#4ade80';

        html += `
            <div style="display: flex; align-items: center; margin-bottom: 4px; font-size: 0.85rem;">
                <span style="width: 60px; color: #888;">${resInfo.position}</span>
                <div style="flex: 1; background: #111; height: 20px; border-radius: 2px; overflow: hidden;">
                    <div style="width: ${barWidth}%; height: 100%; background: ${color};"></div>
                </div>
                <span style="width: 70px; text-align: right; color: ${color};">${resInfo.deviation.toFixed(2)} Å</span>
            </div>
        `;
    }

    html += `
            </div>
        </div>
    `;

    // Add mutations section if available
    if (data.combined_pdb && data.combined_pdb.mutations) {
        html += `
            <div style="margin-bottom: 20px; padding: 15px; background: #0a0a0a; border-radius: 4px;">
                <h4 style="margin-top: 0; color: #65CBF3;">Detected Mutations (${data.combined_pdb.num_mutations})</h4>
        `;

        if (data.combined_pdb.num_mutations > 0) {
            for (const mut of data.combined_pdb.mutations.slice(0, 10)) {
                html += `
                    <div style="font-size: 0.9rem; margin-bottom: 5px; color: #fbbf24;">
                        Position ${mut.position}: ${mut.ref_aa} → ${mut.test_aa}
                    </div>
                `;
            }
            if (data.combined_pdb.num_mutations > 10) {
                html += `<div style="font-size: 0.85rem; color: #888;">... and ${data.combined_pdb.num_mutations - 10} more</div>`;
            }
        } else {
            html += `<div style="color: #4ade80;">No sequence mutations detected (same amino acids)</div>`;
        }

        html += `</div>`;
    }

    // Add download button if PDB was generated
    if (data.combined_pdb && data.combined_pdb.download_url) {
        html += `
            <div style="text-align: center; margin-top: 20px;">
                <a href="${data.combined_pdb.download_url}" download="superposed_comparison.pdb" 
                   style="display: inline-block; background: #2563eb; color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: bold;">
                    📥 Download Aligned PDB (for PyMOL/Chimera)
                </a>
                <div style="margin-top: 10px; font-size: 0.85rem; color: #888;">
                    <strong>For external analysis:</strong> Chain A = Original, Chain B = Mutated<br>
                    B-factor column contains per-residue deviation (Å)
                </div>
            </div>
        `;
    }

    html += `
        <div style="background: #0a0a0a; padding: 10px; border-radius: 4px; font-family: monospace; font-size: 0.85rem; line-height: 1.6; white-space: pre-wrap;">
${data.report}
        </div>
    `;

    content.innerHTML = html;

    // Show modal
    elements.comparisonModal.style.display = 'block';
    elements.modalOverlay.style.display = 'block';

    log('INFO', 'Compare', '✓ Results displayed');
}

function closeComparisonModal() {
    elements.comparisonModal.style.display = 'none';
    elements.modalOverlay.style.display = 'none';
}

// =============================================
// MUTATION DETECTION - Navigate to analysis page
// =============================================

async function showMutations() {
    log('INFO', 'Mutations', 'Navigating to mutation analysis page...');

    const testPath = elements.pathInput.value.trim();
    const refGene = elements.geneInput.value.trim();

    if (!testPath || !refGene) {
        alert('Please enter both test folder path and reference gene ID');
        return;
    }

    try {
        // Get the first PDB file path
        const filesResponse = await fetch(`/api/files?path=${encodeURIComponent(testPath)}`);
        const filesData = await filesResponse.json();

        if (!filesData.pdb_files || filesData.pdb_files.length === 0) {
            alert('No PDB files found in test folder');
            return;
        }

        // Build the mutant PDB path
        const mutantPath = `${testPath}/${filesData.pdb_files[0]}`;

        // Navigate to mutation analysis page with parameters
        const url = `/mutation-analysis?uniprot_id=${encodeURIComponent(refGene)}&mutant_path=${encodeURIComponent(mutantPath)}`;
        window.location.href = url;

    } catch (error) {
        log('ERROR', 'Mutations', `Failed: ${error.message}`);
        alert('Error: ' + error.message);
    }
}

function displayMutations(data) {
    let html = `
        <div style="background: #0a0a0a; padding: 15px; border-radius: 4px; margin-bottom: 20px;">
            <h3 style="margin-top: 0; color: #65CBF3;">Sequence Information</h3>
            <div style="font-size: 0.9rem;">
                <div>Healthy Gene: <strong>${data.healthy_id}</strong> (${data.healthy_length} amino acids)</div>
                <div>Test Sequence: ${data.test_length} amino acids</div>
                <div style="margin-top: 10px; color: ${data.num_mutations === 0 ? '#4ade80' : '#fbbf24'};"><strong>${data.num_mutations} mutations detected</strong></div>
            </div>
        </div>
    `;

    if (data.num_mutations > 0) {
        html += '<div style="background: #0a0a0a; padding: 15px; border-radius: 4px;"><h3 style="margin-top: 0; color: #65CBF3;">Mutations</h3>';

        for (const mut of data.mutations) {
            if (mut.type === 'deletion') {
                html += `<div style="padding: 10px; margin: 5px 0; background: #1a1a1a; border-left: 3px solid #e94560;">
                    <strong style="color: #e94560;">DELETION</strong> at position ${mut.position}: ${mut.count} amino acids removed<br>
                    <span style="font-family: monospace; color: #888;">${mut.sequence}</span>
                </div>`;
            } else if (mut.type === 'insertion') {
                html += `<div style="padding: 10px; margin: 5px 0; background: #1a1a1a; border-left: 3px solid #10b981;">
                    <strong style="color: #10b981;">INSERTION</strong> at position ${mut.position}: ${mut.count} amino acids added<br>
                    <span style="font-family: monospace; color: #888;">${mut.sequence}</span>
                </div>`;
            } else {
                html += `<div style="padding: 10px; margin: 5px 0; background: #1a1a1a; border-left: 3px solid #fbbf24;">
                    Position ${mut.position}: <strong style="color: #fbbf24;">${mut.notation}</strong> (${mut.healthy_aa} → ${mut.mutated_aa})
                </div>`;
            }
        }

        html += '</div>';
    } else {
        html += '<div style="text-align: center; padding: 40px; color: #4ade80;">✓ No mutations found - sequences are identical</div>';
    }

    elements.mutationsContent.innerHTML = html;
    log('INFO', 'Mutations', `✓ Displayed ${data.num_mutations} mutations`);
}

// =============================================
// PATHOGENICITY RESULTS DISPLAY (v3.0)
// =============================================
function displayPathogenicityResults(data) {
    log('INFO', 'Pathogenicity', 'Displaying v3.0 results:', data);

    const verdictColors = {
        danger: '#e94560',
        warning: '#fbbf24',
        success: '#4ade80',
        secondary: '#888',
        info: '#65CBF3'
    };

    const statusColors = {
        'Active': '#4ade80',
        'Disabled': '#888',
        'Error': '#e94560',
        'Not Installed': '#fbbf24'
    };

    const verdictColor = verdictColors[data.verdict_class] || '#888';
    const analysis = data.analysis || {};
    const scanResults = data.scan_results || {};

    let html = `
        <div style="background: #0a0a0a; padding: 20px; border-radius: 8px; margin-top: 20px;">
            
            <!-- HEADER: Mutation Type & Verdict -->
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; padding-bottom: 15px; border-bottom: 1px solid #333;">
                <div>
                    <h3 style="margin: 0; color: #65CBF3; font-size: 1.3rem;">🧬 Mutation Analysis Pipeline</h3>
                    <div style="margin-top: 8px; color: #aaa; font-size: 0.85rem;">
                        Pipeline: <span style="color: #65CBF3; font-weight: bold;">${data.pipeline_decision || 'Unknown'}</span>
                    </div>
                </div>
                <div style="text-align: right;">
                    <div style="background: ${verdictColor}30; padding: 10px 20px; border-radius: 6px; border: 1px solid ${verdictColor};">
                        <div style="font-size: 1.2rem; font-weight: bold; color: ${verdictColor};">${data.verdict || 'UNKNOWN'}</div>
                        <div style="font-size: 0.75rem; color: #aaa; margin-top: 3px;">${data.verdict_reason || ''}</div>
                    </div>
                </div>
            </div>
            
            <!-- SCAN RESULTS CARD -->
            <div style="background: #1a1a1a; padding: 15px; border-radius: 6px; margin-bottom: 15px; border-left: 3px solid #65CBF3;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <strong style="color: #65CBF3;">📊 Scan Results</strong>
                    <span style="background: #2a2a2a; padding: 3px 10px; border-radius: 12px; font-size: 0.8rem; color: #fff;">${data.mutation_type || 'Unknown'}</span>
                </div>
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-top: 10px;">
                    <div>
                        <div style="color: #888; font-size: 0.7rem; text-transform: uppercase;">Detected Mutation</div>
                        <div style="font-family: monospace; font-size: 1.1rem; color: #fff; margin-top: 3px;">${scanResults.detected_mutation || 'None'}</div>
                    </div>
                    <div>
                        <div style="color: #888; font-size: 0.7rem; text-transform: uppercase;">Sequence Identity</div>
                        <div style="font-family: monospace; font-size: 1.1rem; color: #fff; margin-top: 3px;">${scanResults.sequence_identity || 'N/A'}</div>
                    </div>
                    <div>
                        <div style="color: #888; font-size: 0.7rem; text-transform: uppercase;">Length (WT/Mut)</div>
                        <div style="font-family: monospace; font-size: 1.1rem; color: #fff; margin-top: 3px;">${scanResults.wt_length || '?'}/${scanResults.mut_length || '?'}</div>
                    </div>
                </div>
            </div>
            
            <!-- CRITICAL FAILURE ALERT (for Frameshift/Duplication) -->
            ${data.status === 'CRITICAL_FAILURE' || data.pipeline_decision === 'AUTO_FAIL' ? `
                <div style="background: #e9456022; padding: 20px; border-radius: 6px; margin-bottom: 15px; border: 2px solid #e94560; text-align: center;">
                    <div style="font-size: 2rem; margin-bottom: 10px;">⚠️</div>
                    <div style="font-size: 1.1rem; font-weight: bold; color: #e94560; margin-bottom: 8px;">
                        ${data.mutation_type === 'Frameshift' ? 'READING FRAME DESTROYED' : 'TOXIC AGGREGATION RISK'}
                    </div>
                    <div style="color: #ccc; font-size: 0.9rem;">
                        ${data.mutation_type === 'Frameshift'
                ? 'Frameshift mutation scrambles the entire protein sequence after the mutation point. Protein synthesis fails or produces non-functional protein.'
                : 'Repeat expansion detected. Large duplications cause protein aggregation (clumping), leading to toxic cellular effects.'}
                    </div>
                    <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #e9456044; color: #888; font-size: 0.8rem;">
                        All analysis tools disabled - structural comparison not meaningful for this mutation type.
                    </div>
                </div>
            ` : ''}
            
            <!-- TOOL CARDS CONTAINER -->
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px;">
    `;

    // --- TOOL CARD 1: AlphaMissense ---
    const am = analysis.alphamissense || { active: false, status: 'Unknown' };
    const amActive = am.active;
    const amStatusColor = statusColors[am.status] || '#888';
    const amBorderColor = amActive ? (am.class === 'PATHOGENIC' ? '#e94560' : '#4ade80') : '#444';

    html += `
        <div style="background: #1a1a1a; padding: 15px; border-radius: 6px; border-top: 3px solid ${amBorderColor}; opacity: ${amActive ? '1' : '0.6'};">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <strong style="color: #fff;">🧠 AlphaMissense</strong>
                <span style="background: ${amStatusColor}30; color: ${amStatusColor}; padding: 2px 8px; border-radius: 10px; font-size: 0.7rem;">${am.status || 'Unknown'}</span>
            </div>
            ${amActive ? `
                <div style="text-align: center; padding: 15px 0;">
                    <div style="font-size: 2rem; font-weight: bold; color: ${amBorderColor};">${am.score !== null && am.score !== undefined ? am.score.toFixed(2) : 'N/A'}</div>
                    <div style="font-size: 0.9rem; color: ${amBorderColor}; margin-top: 5px;">${am.verdict || am.class || 'Unknown'}</div>
                </div>
                <div style="color: #888; font-size: 0.75rem; text-align: center; border-top: 1px solid #333; padding-top: 10px;">${am.reason || ''}</div>
            ` : `
                <div style="text-align: center; padding: 20px 10px; color: #666;">
                    <div style="font-size: 0.85rem;">${am.reason || 'Not available'}</div>
                </div>
            `}
        </div>
    `;

    // --- TOOL CARD 2: FoldX ---
    const fx = analysis.foldx || { active: false, status: 'Unknown' };
    const fxActive = fx.active;
    const fxStatusColor = statusColors[fx.status] || '#888';
    const fxBorderColor = fxActive ? (fx.ddg > 1.6 ? '#e94560' : fx.ddg > 0.5 ? '#fbbf24' : '#4ade80') : '#444';

    html += `
        <div style="background: #1a1a1a; padding: 15px; border-radius: 6px; border-top: 3px solid ${fxBorderColor}; opacity: ${fxActive ? '1' : '0.6'};">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <strong style="color: #fff;">🔬 FoldX Stability</strong>
                <span style="background: ${fxStatusColor}30; color: ${fxStatusColor}; padding: 2px 8px; border-radius: 10px; font-size: 0.7rem;">${fx.status || 'Unknown'}</span>
            </div>
            ${fxActive ? `
                <div style="text-align: center; padding: 10px 0;">
                    <div style="font-size: 1.8rem; font-weight: bold; color: ${fxBorderColor};">ΔΔG: ${fx.ddg !== null && fx.ddg !== undefined ? (fx.ddg > 0 ? '+' : '') + fx.ddg.toFixed(2) : 'N/A'}</div>
                    <div style="font-size: 0.85rem; color: ${fxBorderColor}; margin-top: 5px;">${fx.stability_verdict || 'Unknown'}</div>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 10px; padding-top: 10px; border-top: 1px solid #333;">
                    <div style="text-align: center;">
                        <div style="color: #888; font-size: 0.65rem;">WT Energy</div>
                        <div style="font-family: monospace; font-size: 0.85rem;">${fx.energy_wildtype !== null && fx.energy_wildtype !== undefined ? fx.energy_wildtype.toFixed(1) : 'N/A'}</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="color: #888; font-size: 0.65rem;">Mut Energy</div>
                        <div style="font-family: monospace; font-size: 0.85rem;">${fx.energy_mutant !== null && fx.energy_mutant !== undefined ? fx.energy_mutant.toFixed(1) : 'N/A'}</div>
                    </div>
                </div>
            ` : `
                <div style="text-align: center; padding: 20px 10px; color: #666;">
                    <div style="font-size: 0.85rem;">${fx.reason || 'Not available'}</div>
                </div>
            `}
        </div>
    `;

    // --- TOOL CARD 3: TM-align ---
    const tm = analysis.tmalign || { active: false, status: 'Unknown' };
    const tmActive = tm.active;
    const tmStatusColor = statusColors[tm.status] || '#888';
    const tmBorderColor = tmActive ? (tm.tm_score >= 0.5 ? '#4ade80' : '#e94560') : '#444';

    html += `
        <div style="background: #1a1a1a; padding: 15px; border-radius: 6px; border-top: 3px solid ${tmBorderColor}; opacity: ${tmActive ? '1' : '0.6'};">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <strong style="color: #fff;">📐 TM-align</strong>
                <span style="background: ${tmStatusColor}30; color: ${tmStatusColor}; padding: 2px 8px; border-radius: 10px; font-size: 0.7rem;">${tm.status || 'Unknown'}</span>
            </div>
            ${tmActive ? `
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; padding: 10px 0;">
                    <div style="text-align: center;">
                        <div style="font-size: 1.5rem; font-weight: bold; color: ${tmBorderColor};">${tm.tm_score !== null && tm.tm_score !== undefined ? tm.tm_score.toFixed(2) : 'N/A'}</div>
                        <div style="color: #888; font-size: 0.75rem;">TM-score</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: 1.5rem; font-weight: bold; color: #fff;">${tm.rmsd !== null && tm.rmsd !== undefined ? tm.rmsd.toFixed(2) : 'N/A'}</div>
                        <div style="color: #888; font-size: 0.75rem;">RMSD (Å)</div>
                    </div>
                </div>
                <div style="color: #888; font-size: 0.75rem; text-align: center; border-top: 1px solid #333; padding-top: 10px;">${tm.structure_verdict || ''} - ${tm.reason || ''}</div>
            ` : `
                <div style="text-align: center; padding: 20px 10px; color: #666;">
                    <div style="font-size: 0.85rem;">${tm.reason || 'Not available'}</div>
                </div>
            `}
        </div>
    `;

    html += `
            </div>
        </div>
    `;

    elements.mutationsContent.innerHTML += html;
    log('INFO', 'Pathogenicity', '✓ v3.0 Results displayed');
}

function closeMutationsModal() {
    if (elements.mutationsModal) {
        elements.mutationsModal.style.display = 'none';
    }
    if (elements.modalOverlay) {
        elements.modalOverlay.style.display = 'none';
    }
}

// ============================================='s
// START
// =============================================
log('INFO', 'App', 'Starting application...');
init();
