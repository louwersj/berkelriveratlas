[out:json][timeout:{{overpass_timeout_seconds}}];
way["waterway"~"river|stream|canal"]({{bbox_south}},{{bbox_west}},{{bbox_north}},{{bbox_east}})->.berkel_waterways;
(
  way(around.berkel_waterways:{{riverbank_building_distance_m}})["building"];
  relation(around.berkel_waterways:{{riverbank_building_distance_m}})["building"];
);
out body;
>;
out skel qt;
