[out:json][timeout:{{overpass_timeout_seconds}}];
(
  way["highway"]({{bbox_south}},{{bbox_west}},{{bbox_north}},{{bbox_east}});
);
out body;
>;
out skel qt;
