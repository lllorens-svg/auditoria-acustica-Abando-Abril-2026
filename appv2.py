<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Abando Aurrera - Auditoría Acústica</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/luxon@3.4.4/build/global/luxon.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-luxon@1.3.1"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-annotation@3.0.1"></script>
    <style>
        .active-tab { border-bottom: px solid #ef4444; color: #ef4444; }
        .chart-wrapper { height: 350px; position: relative; }
        .loading-spinner {
            border: 3px solid rgba(255,255,255,0.3);
            border-radius: 50%;
            border-top-color: #fff;
            width: 20px;
            height: 20px;
            animation: spin 1s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
    </style>
</head>
<body class="bg-slate-50 text-slate-900 font-sans">

    <!-- Header Institucional -->
    <header class="bg-[#003366] text-white shadow-lg border-b-4 border-red-600">
        <div class="container mx-auto px-6 py-4 flex flex-col md:flex-row justify-between items-center">
            <div class="flex items-center gap-4">
                <div class="bg-white p-2 rounded shadow-md">
                    <span class="text-[#003366] font-black text-xl tracking-tighter">BILBAO</span>
                </div>
                <div>
                    <h1 class="text-xl font-bold">Abando Aurrera: Monitorización Acústica</h1>
                    <p class="text-xs text-blue-200 uppercase tracking-widest font-semibold">Participación Ciudadana y Calidad Ambiental</p>
                </div>
            </div>
            <div id="syncIndicator" class="mt-4 md:mt-0 flex items-center gap-3 bg-blue-900/50 px-4 py-2 rounded-full border border-blue-400/30">
                <div id="statusDot" class="w-3 h-3 rounded-full bg-slate-400"></div>
                <span id="statusLabel" class="text-[10px] font-black uppercase tracking-widest">Sin datos cargados</span>
            </div>
        </div>
    </header>

    <div class="container mx-auto p-6 flex flex-col lg:flex-row gap-8">
        
        <!-- Sidebar de Control -->
        <aside class="lg:w-1/4 space-y-6">
            <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
                <h2 class="text-xs font-black text-slate-400 uppercase mb-4 tracking-widest italic">Panel de Control</h2>
                
                <div class="space-y-4">
                    <button onclick="fetchOpenData()" id="btnSync" class="w-full bg-red-600 hover:bg-red-700 text-white font-bold py-3 px-4 rounded-xl transition-all shadow-md flex items-center justify-center gap-3 group active:scale-95">
                        <span id="syncIcon" class="text-xl group-hover:rotate-180 transition-transform duration-500">📡</span>
                        <span id="btnText">Sincronizar Datos</span>
                        <div id="btnSpinner" class="loading-spinner hidden"></div>
                    </button>

                    <div class="relative py-2">
                        <div class="absolute inset-0 flex items-center"><span class="w-full border-t border-slate-100"></span></div>
                        <div class="relative flex justify-center text-[10px] font-black text-slate-300 uppercase bg-white px-2">O carga manual</div>
                    </div>

                    <label class="block w-full border-2 border-dashed border-slate-200 rounded-xl p-4 text-center cursor-pointer hover:border-blue-400 hover:bg-blue-50 transition-all">
                        <span class="text-2xl block mb-1">📁</span>
                        <span class="text-[10px] font-black text-slate-500 uppercase">Subir CSV</span>
                        <input type="file" id="csvInput" accept=".csv" class="hidden">
                    </label>

                    <div class="pt-4 border-t border-slate-100">
                        <label class="block text-[10px] font-black text-slate-500 uppercase mb-2">Rango de Fechas</label>
                        <div class="grid grid-cols-1 gap-2">
                            <input type="date" id="dateStart" class="w-full p-2 text-xs border rounded-lg font-bold outline-none focus:ring-2 focus:ring-blue-500">
                            <input type="date" id="dateEnd" class="w-full p-2 text-xs border rounded-lg font-bold outline-none focus:ring-2 focus:ring-blue-500">
                        </div>
                    </div>
                </div>
            </div>

            <div class="bg-blue-50 p-4 rounded-xl border border-blue-100">
                <h4 class="text-[10px] font-black text-blue-800 uppercase mb-2">Información</h4>
                <p class="text-[10px] text-blue-700 leading-relaxed italic">
                    Datos obtenidos del portal Open Data Bilbao. Se analizan los niveles <b>LAeq</b> cada 15 min. Límites legales: 65dB día / 55dB noche.
                </p>
            </div>
        </aside>

        <!-- Área Principal -->
        <main class="lg:w-3/4">
            <!-- Tabs -->
            <nav class="flex gap-8 mb-8 border-b border-slate-200">
                <button onclick="showTab('calidad')" id="tab-calidad" class="pb-4 text-xs font-black uppercase tracking-widest active-tab">Estado de Sensores</button>
                <button onclick="showTab('analisis')" id="tab-analisis" class="pb-4 text-xs font-black uppercase tracking-widest text-slate-400 hover:text-slate-600">Gráficas Detalladas</button>
                <button onclick="showTab('ranking')" id="tab-ranking" class="pb-4 text-xs font-black uppercase tracking-widest text-slate-400 hover:text-slate-600">Impactos Críticos</button>
            </nav>

            <!-- Sección Calidad -->
            <div id="sec-calidad" class="space-y-6">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 h-80">
                        <h3 class="text-xs font-black uppercase text-slate-500 mb-4 tracking-tighter">Disponibilidad de Datos</h3>
                        <canvas id="qualityChart"></canvas>
                    </div>
                    <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 h-80 flex flex-col items-center justify-center text-center">
                        <div id="statsSummary" class="space-y-4">
                            <p class="text-xs font-bold text-slate-400 uppercase tracking-widest">Sensores con Actividad</p>
                            <p id="activeCount" class="text-6xl font-black text-blue-900">0</p>
                            <p id="coverageSummary" class="text-[10px] text-slate-500 font-medium px-8 italic">Seleccione un rango de fechas para ver el rendimiento de la red.</p>
                        </div>
                    </div>
                </div>
                <div id="qualityGrid" class="grid grid-cols-2 md:grid-cols-4 gap-4"></div>
            </div>

            <!-- Sección Análisis -->
            <div id="sec-analisis" class="hidden space-y-6">
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
                    <div class="flex flex-col md:flex-row justify-between items-center gap-4 mb-6">
                        <h3 id="sensorTitle" class="text-lg font-black text-slate-800">Seleccione un Punto</h3>
                        <select id="sensorSelector" class="p-2 text-xs border border-slate-200 rounded-lg bg-slate-50 font-bold min-w-[250px]">
                            <option value="">Cargue datos primero...</option>
                        </select>
                    </div>
                    
                    <div id="chartsPlaceholder" class="py-20 text-center space-y-4">
                        <div class="text-4xl">📊</div>
                        <p class="text-xs font-black text-slate-300 uppercase italic">Elija una ubicación para ver la serie histórica</p>
                    </div>

                    <div id="actualCharts" class="hidden space-y-10">
                        <div class="chart-wrapper">
                            <h4 class="text-[10px] font-black uppercase text-orange-600 mb-2">Nivel Diurno (07:00 - 23:00)</h4>
                            <canvas id="chartDay"></canvas>
                        </div>
                        <div class="chart-wrapper border-t pt-8">
                            <h4 class="text-[10px] font-black uppercase text-indigo-600 mb-2">Nivel Nocturno (23:00 - 07:00)</h4>
                            <canvas id="chartNight"></canvas>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Sección Ranking -->
            <div id="sec-ranking" class="hidden space-y-6">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
                        <h3 class="text-xs font-black text-orange-600 uppercase mb-6 border-b pb-2">Puntos Críticos: Día (Lmax)</h3>
                        <div id="rankDay" class="space-y-3"></div>
                    </div>
                    <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
                        <h3 class="text-xs font-black text-indigo-600 uppercase mb-6 border-b pb-2">Puntos Críticos: Noche (Lmax)</h3>
                        <div id="rankNight" class="space-y-3"></div>
                    </div>
                </div>
            </div>

        </main>
    </div>

    <script>
        const SENSORES_ABANDO = {
            'BI-RUI-001': 'RODRIGUEZ ARIAS', 'BI-RUI-020': 'POZA 48', 'BI-RUI-021': 'POZA 53',
            'BI-RUI-022': 'POZA 30', 'BI-RUI-025': 'PRINCIPE 1', 'BI-RUI-BR15': 'ALAMEDA URQUIJO',
            'BI-RUI-BR2': 'FRENTE IGLESIA', 'BI-RUI-C001': 'URIBITARTE 1', 'BI-RUI-C002': 'URIBITARTE 6',
            'BI-RUI-C003': 'MUELLE RIPA', 'BI-RUI-C004': 'ESCALINATAS DE URIBITARTE', 'BI-RUI-C008': 'RIPA 5',
            'BI-RUI-C010': 'ARBOLANTXA', 'BI-RUI-C011': 'JARDINES DE ALBIA', 'BI-RUI-C012': 'IBAÑEZ DE BILBAO',
            'BI-RUI-C013': 'COLÓN DE LARREÁTEGUI', 'BI-RUI-C014': 'IPARRAGUIRRE 16', 'BI-RUI-C015': 'JUAN DE AJURIAGUERRA',
            'BI-RUI-C016': 'DIPUTACIÓN 4', 'BI-RUI-C017': 'BERASTEGUI 4', 'BI-RUI-C018': 'LEDESMA 6',
            'BI-RUI-C019': 'LEDESMA 7', 'BI-RUI-C020': 'LEDESMA 10 bis', 'BI-RUI-C021': 'LEDESMA 30',
            'BI-RUI-C022': 'VILLARIAS 2', 'BI-RUI-C025': 'LUIS BRIÑAS', 'BI-RUI-C030': 'EGAÑA KALEA 6',
            'BI-RUI-C031': 'EGAÑA KALEA 22', 'BI-RUI-C032': 'PARTICULAR INDAUTXU', 'BI-RUI-C033': 'MAESTRO GARCÍA RIVERO',
            'BI-RUI-C034': 'ARETXABALETA 6', 'BI-RUI-P009': 'ALAMEDA RECALDE'
        };

        const URL_CSV = "https://www.bilbao.eus/aytoonline/jsp/opendata/movilidad/od_sonometro_mediciones.jsp?idioma=c&formato=csv";
        let mediciones = [];
        let chartInstances = {};

        async function fetchOpenData() {
            setLoading(true);
            const proxy = `https://api.allorigins.win/raw?url=${encodeURIComponent(URL_CSV)}`;
            try {
                const response = await fetch(proxy);
                if (!response.ok) throw new Error('Error en respuesta');
                const csvText = await response.text();
                processCSV(csvText);
                updateIndicator('success');
            } catch (e) {
                console.error(e);
                updateIndicator('error');
                // No usamos alert() por compatibilidad con el entorno
            }
            setLoading(false);
        }

        function processCSV(text) {
            if (!text || text.length < 50) return;
            const rows = text.split(/\r?\n/);
            const delimiter = rows[0].includes(';') ? ';' : ',';
            const headers = rows[0].split(delimiter).map(h => h.trim().toUpperCase());

            const idxID = headers.findIndex(h => h.includes('CODIGO') || h.includes('ID'));
            const idxVal = headers.findIndex(h => h.includes('DECIBELIOS') || h.includes('LAEQ'));
            const idxDate = headers.findIndex(h => h.includes('FECHA') || h.includes('HORA'));

            const dataParsed = [];
            for (let i = 1; i < rows.length; i++) {
                const cols = rows[i].split(delimiter);
                if (cols.length < 3) continue;
                const id = cols[idxID]?.trim();
                if (SENSORES_ABANDO[id]) {
                    const db = parseFloat(cols[idxVal]?.replace(',', '.'));
                    const rawDate = cols[idxDate]?.trim().replace(" ", "T");
                    const dt = luxon.DateTime.fromISO(rawDate);
                    if (dt.isValid && !isNaN(db)) {
                        dataParsed.push({
                            id, name: SENSORES_ABANDO[id], dt, val: db,
                            periodo: (dt.hour >= 7 && dt.hour < 23) ? 'DIA' : 'NOCHE'
                        });
                    }
                }
            }
            mediciones = dataParsed.sort((a,b) => a.dt - b.dt);
            if (mediciones.length > 0) {
                document.getElementById('dateStart').value = mediciones[0].dt.toISODate();
                document.getElementById('dateEnd').value = mediciones[mediciones.length-1].dt.toISODate();
                refreshUI();
            }
        }

        function refreshUI() {
            const startStr = document.getElementById('dateStart').value;
            const endStr = document.getElementById('dateEnd').value;
            if (!startStr || !endStr) return;

            const start = luxon.DateTime.fromISO(startStr).startOf('day');
            const end = luxon.DateTime.fromISO(endStr).endOf('day');
            const filtered = mediciones.filter(m => m.dt >= start && m.dt <= end);
            
            updateQuality(filtered);
            updateSensorList(filtered);
            updateRankings(filtered);
            const sel = document.getElementById('sensorSelector').value;
            if (sel) updateCharts(sel);
        }

        function updateQuality(data) {
            const counts = {};
            Object.keys(SENSORES_ABANDO).forEach(id => counts[id] = 0);
            data.forEach(m => counts[m.id]++);
            const activos = Object.values(counts).filter(c => c > 0).length;
            document.getElementById('activeCount').textContent = activos;

            const ctx = document.getElementById('qualityChart').getContext('2d');
            if (chartInstances.quality) chartInstances.quality.destroy();
            chartInstances.quality = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: Object.keys(counts).map(id => SENSORES_ABANDO[id]),
                    datasets: [{ label: 'Registros', data: Object.values(counts), backgroundColor: '#3b82f6' }]
                },
                options: { indexAxis: 'y', maintainAspectRatio: false, plugins: { legend: { display: false } } }
            });

            document.getElementById('qualityGrid').innerHTML = Object.entries(counts).map(([id, count]) => `
                <div class="bg-white p-3 rounded-xl border border-slate-100 shadow-sm">
                    <p class="text-[8px] font-black text-slate-400 uppercase">${id}</p>
                    <p class="text-[10px] font-bold truncate">${SENSORES_ABANDO[id]}</p>
                    <div class="mt-1 flex justify-between items-center">
                        <span class="text-[10px] font-black ${count > 0 ? 'text-green-500' : 'text-slate-300'}">${count > 0 ? 'OK' : 'OFF'}</span>
                        <span class="text-[8px] font-mono text-slate-400">${count} pts</span>
                    </div>
                </div>
            `).join('');
        }

        function updateSensorList(data) {
            const sel = document.getElementById('sensorSelector');
            const currentVal = sel.value;
            const ids = [...new Set(data.map(m => m.id))];
            sel.innerHTML = '<option value="">Seleccione una calle...</option>';
            ids.forEach(id => {
                const opt = document.createElement('option');
                opt.value = id; opt.textContent = SENSORES_ABANDO[id];
                if (id === currentVal) opt.selected = true;
                sel.appendChild(opt);
            });
        }

        function updateCharts(sid) {
            if (!sid) return;
            document.getElementById('chartsPlaceholder').classList.add('hidden');
            document.getElementById('actualCharts').classList.remove('hidden');
            document.getElementById('sensorTitle').textContent = SENSORES_ABANDO[sid];
            
            const start = luxon.DateTime.fromISO(document.getElementById('dateStart').value).startOf('day');
            const end = luxon.DateTime.fromISO(document.getElementById('dateEnd').value).endOf('day');
            const sData = mediciones.filter(m => m.id === sid && m.dt >= start && m.dt <= end);
            
            renderLine('chartDay', sData.filter(m => m.periodo === 'DIA'), '#ea580c', 65);
            renderLine('chartNight', sData.filter(m => m.periodo === 'NOCHE'), '#4f46e5', 55);
        }

        function renderLine(cid, data, color, limit) {
            const ctx = document.getElementById(cid).getContext('2d');
            if (chartInstances[cid]) chartInstances[cid].destroy();
            chartInstances[cid] = new Chart(ctx, {
                type: 'line',
                data: { datasets: [{ data: data.map(m => ({ x: m.dt.toMillis(), y: m.val })), borderColor: color, borderWidth: 1.5, pointRadius: 0, fill: false }] },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    scales: { x: { type: 'time', time: { unit: 'day' } }, y: { min: 35, max: 90 } },
                    plugins: { 
                        legend: { display: false },
                        annotation: { annotations: { l: { type: 'line', yMin: limit, yMax: limit, borderColor: 'red', borderDash: [5,5] } } }
                    }
                }
            });
        }

        function updateRankings(data) {
            const getRank = (sub) => {
                const maxBySensor = {};
                sub.forEach(m => {
                    if (!maxBySensor[m.id] || m.val > maxBySensor[m.id].val) {
                        maxBySensor[m.id] = { val: m.val, dt: m.dt.toFormat('dd/MM HH:mm') };
                    }
                });
                return Object.entries(maxBySensor)
                    .map(([id, info]) => ({ name: SENSORES_ABANDO[id], val: info.val, time: info.dt }))
                    .sort((a,b) => b.val - a.val).slice(0, 5);
            };

            const renderRank = (list, target) => {
                document.getElementById(target).innerHTML = list.map((item, i) => `
                    <div class="flex items-center justify-between p-3 bg-slate-50 rounded-xl border border-slate-100">
                        <div>
                            <p class="text-xs font-bold text-slate-800">${item.name}</p>
                            <p class="text-[9px] text-slate-400 font-mono">${item.time}</p>
                        </div>
                        <span class="text-xs font-black text-slate-900">${item.val.toFixed(1)} <span class="text-[9px]">dB</span></span>
                    </div>
                `).join('') || '<p class="text-xs italic text-slate-400">Sin datos registrados</p>';
            };

            renderRank(getRank(data.filter(m => m.periodo === 'DIA')), 'rankDay');
            renderRank(getRank(data.filter(m => m.periodo === 'NOCHE')), 'rankNight');
        }

        function showTab(id) {
            ['calidad', 'analisis', 'ranking'].forEach(t => {
                document.getElementById('sec-' + t).classList.add('hidden');
                const btn = document.getElementById('tab-' + t);
                btn.classList.remove('active-tab');
                btn.classList.add('text-slate-400');
            });
            document.getElementById('sec-' + id).classList.remove('hidden');
            const activeBtn = document.getElementById('tab-' + id);
            activeBtn.classList.add('active-tab');
            activeBtn.classList.remove('text-slate-400');
        }

        function setLoading(l) {
            document.getElementById('btnSync').disabled = l;
            document.getElementById('btnSpinner').classList.toggle('hidden', !l);
            document.getElementById('btnText').textContent = l ? "Sincronizando..." : "Sincronizar Datos";
        }

        function updateIndicator(s) {
            const dot = document.getElementById('statusDot');
            dot.className = `w-3 h-3 rounded-full ${s === 'success' ? 'bg-green-500' : 'bg-red-500'}`;
            document.getElementById('statusLabel').textContent = s === 'success' ? 'Sincronizado' : 'Error';
        }

        document.getElementById('csvInput').addEventListener('change', (e) => {
            const f = e.target.files[0];
            if (f) { const r = new FileReader(); r.onload = (ev) => processCSV(ev.target.result); r.readAsText(f); }
        });
        document.getElementById('sensorSelector').addEventListener('change', (e) => updateCharts(e.target.value));
        document.getElementById('dateStart').addEventListener('change', refreshUI);
        document.getElementById('dateEnd').addEventListener('change', refreshUI);
    </script>
</body>
</html>
