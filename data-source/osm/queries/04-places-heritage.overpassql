[out:json][timeout:{{overpass_timeout_seconds}}];
(
  node["historic"]({{bbox_south}},{{bbox_west}},{{bbox_north}},{{bbox_east}});
  way["historic"]({{bbox_south}},{{bbox_west}},{{bbox_north}},{{bbox_east}});
  relation["historic"]({{bbox_south}},{{bbox_west}},{{bbox_north}},{{bbox_east}});
);
out body;
>;
out skel qt;
