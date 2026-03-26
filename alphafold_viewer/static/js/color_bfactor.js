// Color by B-factor (for deviation visualization)
async function colorByBfactor(viewer) {
    log('INFO', 'Color', 'Coloring by B-factor (deviation)...');

    try {
        const plugin = viewer.plugin || viewer;

        // Custom color scheme: 0 (green) -> 50 (yellow) -> 100 (red)
        const colorCommand = plugin.build().to(plugin.managers.structure.hierarchy.current.structures[0])
            .apply(molstar.StateTransforms.Representation.StructureRepresentation3D, {
                type: {
                    name: 'cartoon',
                    params: {
                        alpha: 1.0
                    }
                },
                colorTheme: {
                    name: 'uncertainty',  // This uses B-factor
                    params: {}
                }
            });

        await colorCommand.commit();
        log('INFO', 'Color', '✓ B-factor coloring applied');
    } catch (e) {
        log('WARN', 'Color', `B-factor coloring failed: ${e.message}`);
    }
}
