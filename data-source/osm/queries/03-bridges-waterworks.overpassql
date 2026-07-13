[out:json][timeout:{{overpass_timeout_seconds}}];
(
  node["man_made"~"weir|dam|sluice|lock_gate|watermill|pump"]({{bbox_south}},{{bbox_west}},{{bbox_north}},{{bbox_east}});
  way["man_made"~"weir|dam|sluice|lock_gate|watermill|pump"]({{bbox_south}},{{bbox_west}},{{bbox_north}},{{bbox_east}});
  node["waterway"~"weir|dam|lock_gate|sluice"]({{bbox_south}},{{bbox_west}},{{bbox_north}},{{bbox_east}});
  way["waterway"~"weir|dam|lock_gate|sluice"]({{bbox_south}},{{bbox_west}},{{bbox_north}},{{bbox_east}});
  way["bridge"]({{bbox_south}},{{bbox_west}},{{bbox_north}},{{bbox_east}});
);
out body;
>;
out skel qt;
