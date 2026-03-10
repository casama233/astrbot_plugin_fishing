document.addEventListener('DOMContentLoaded', function () {
    const itemModal = document.getElementById('fishModal');
    if (!itemModal) return;

    const modalTitle = itemModal.querySelector('.modal-title');
    const form = itemModal.querySelector('#fish-form');

    document.getElementById('addFishBtn').addEventListener('click', function () {
        modalTitle.textContent = '添加新鱼';
        form.action = addUrl; // 使用从HTML传入的全局变量
        form.reset();
        const idField = form.querySelector('#fish_id');
        if (idField) idField.value = '';
    });

    document.querySelectorAll('.edit-btn').forEach(button => {
        button.addEventListener('click', function () {
            const data = JSON.parse(this.dataset.itemJson);
            modalTitle.textContent = `编辑鱼类: ${data.name}`;
            form.action = `${editUrlBase}/${data.fish_id}`; // 使用从HTML传入的全局变量
            for (const key in data) {
                if (form.elements[key]) {
                    const value = Array.isArray(data[key]) ? data[key].join(',') : data[key];
                    form.elements[key].value = value || '';
                }
            }
            const idField = form.querySelector('#fish_id');
            if (idField) idField.value = data.fish_id || '';
        });
    });

    // Auto-apply limited zones to zone manager when available_zones is set
    const availableZonesInput = document.getElementById('available_zones');
    const pushFishToZones = () => {
        if (!availableZonesInput) return;
        const value = availableZonesInput.value || '';
        const zoneIds = value
            .split(',')
            .map(v => parseInt(v.trim(), 10))
            .filter(v => !Number.isNaN(v));
        if (!zoneIds.length) return;
        const fishId = parseInt(form.querySelector('#fish_id')?.value || '', 10);
        if (!fishId) return;
        fetch('/admin/api/zones/assign-fish', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fish_id: fishId, zone_ids: zoneIds })
        }).catch(() => {});
    };
    if (availableZonesInput) {
        availableZonesInput.addEventListener('change', pushFishToZones);
        form.addEventListener('submit', () => {
            setTimeout(pushFishToZones, 300);
        });
    }
});
